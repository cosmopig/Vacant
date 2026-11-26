#!/usr/bin/env python3
"""ops.fl.run_fl — Fast-lane single-round code experiment runner (B0/B0x3/GT/EX/TF/XM/MV/CT).

Reuses `ops.e1` by import:
- Claude worker sandbox (`build_claude_worker_bwrap_argv`, `prepare_claude_credentials`, `run_sandboxed`, `kill_all_live`)
- Host UNIX-socket allowlist proxy (`AllowlistUnixProxy`)
- Claude CLI argv & stream-json usage/cost parser (`build_claude_cli_argv`, `usage_from_claude_log`)
- Preflight Claude negative controls (`run_claude_negative_controls`)
- Git clean guard helper (`_git`) and atomic file helpers

Usage:
  python3 ops/fl/run_fl.py --plan ops/fl/plans/PLAN.json --root /tmp/fl_run [--calibrate N]
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import pathlib
import shutil
import sys
import tempfile
import threading
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from ops.e1.negative_controls import run_claude_negative_controls
from ops.e1.netproxy import AllowlistUnixProxy
from ops.e1.run_e1 import (
    _INFRA_ERR_RE,
    _canonical_json,
    _git,
    _parse_allowed_connect_hosts,
    build_claude_cli_argv,
    usage_from_claude_log,
)
from ops.e1.sandbox import (
    build_claude_worker_bwrap_argv,
    kill_all_live,
    prepare_claude_credentials,
    run_sandboxed,
)
from ops.fl import (
    ARMS_FL,
    DEFAULT_BANK_PATH,
    DEFAULT_INDEX_PATH,
    PLAN_SCHEMA,
    REPO_ROOT,
    RESULT_SCHEMA,
    RUN_SCHEMA,
    assert_ks1_clean,
    atomic_write_json,
    atomic_write_text,
    sha256_bytes,
    utc_now_iso,
)
from ops.fl.bank import load_bank_tasks, parse_tests_spec_text
from ops.fl.eval_fl import (
    cluster_mv_outputs,
    collect_outputs_in_sandbox,
    deduplicate_encoded_inputs,
    encode_val_host,
    evaluate_solution_on_cases,
    run_input_generator_in_sandbox,
    score_ct_solutions,
)

_LOCK = threading.Lock()

# Harness-authored prompt suffixes (validated against KS-1)
_TASK_SUFFIX_FMT = "Write the function `{entry_point}` in /work/solution.py."
_B0X3_RETRY_SUFFIX = "Review your solution.py and improve it if needed."
_TF_RO_SPEC_NOTE = (
    "A read-only test specification file `/work/tests_spec.py` is present in your workspace; "
    "you may read it, and it cannot be modified."
)
_TEST_WRITER_SUFFIX_FMT = (
    "Do NOT write a solution or /work/solution.py. "
    "Write ONLY `/work/tests_spec.py` containing a single Python literal list of 5 to 15 test cases "
    "for `{entry_point}` (covering statement examples, typical inputs, and edge cases). "
    "Format: a Python list of dicts, each with keys `'args'` (list of positional arguments passed as "
    "`{entry_point}(*args)`) and `'expected'` (exact expected return value), for example:\n"
    "[\n"
    "    {{\"args\": [...], \"expected\": ...}},\n"
    "]\n"
    "Use ONLY Python literals (no imports, no function definitions, no function calls, no executable code)."
)
_INPUT_GEN_SUFFIX_FMT = (
    "Do NOT write a solution and do NOT compute expected outputs. "
    "Write ONLY `/work/gen_inputs.py` defining a function `gen_inputs()` that returns a list of {n_inputs} "
    "diverse, valid input argument tuples/lists for `{entry_point}` (covering small, edge, and typical inputs "
    "within the problem constraints; keep each input small enough to run quickly). "
    "Each element of the returned list MUST be a tuple or list of positional arguments to pass as "
    "`{entry_point}(*args)` (even for a 1-argument function, wrap each argument in a 1-element list/tuple). "
    "Use only the Python standard library and deterministic generation (fixed random seed if using random)."
)

# Verify harness-authored templates are KS-1 clean at import time
for _tmpl in (
    _TASK_SUFFIX_FMT.format(entry_point="fn"),
    _B0X3_RETRY_SUFFIX,
    _TF_RO_SPEC_NOTE,
    _TEST_WRITER_SUFFIX_FMT.format(entry_point="fn"),
    _INPUT_GEN_SUFFIX_FMT.format(entry_point="fn", n_inputs=20),
):
    assert_ks1_clean(_tmpl)


def build_task_prompt(task: dict[str, Any]) -> str:
    """Identical base task text across all arms."""
    suffix = _TASK_SUFFIX_FMT.format(entry_point=task["entry_point"])
    assert_ks1_clean(suffix)
    return f"{task['prompt'].rstrip()}\n\n{suffix}"


def build_b0x3_retry_prompt(task: dict[str, Any]) -> str:
    assert_ks1_clean(_B0X3_RETRY_SUFFIX)
    return f"{build_task_prompt(task)}\n\n{_B0X3_RETRY_SUFFIX}"


def build_tf_coder_prompt(task: dict[str, Any]) -> str:
    assert_ks1_clean(_TF_RO_SPEC_NOTE)
    return f"{build_task_prompt(task)}\n\n{_TF_RO_SPEC_NOTE}"


def build_test_writer_prompt(task: dict[str, Any]) -> str:
    suffix = _TEST_WRITER_SUFFIX_FMT.format(entry_point=task["entry_point"])
    assert_ks1_clean(suffix)
    return f"{task['prompt'].rstrip()}\n\n{suffix}"


def build_input_gen_prompt(task: dict[str, Any], *, n_inputs: int = 20) -> str:
    suffix = _INPUT_GEN_SUFFIX_FMT.format(entry_point=task["entry_point"], n_inputs=n_inputs)
    assert_ks1_clean(suffix)
    return f"{task['prompt'].rstrip()}\n\n{suffix}"


def insert_work_ro_binds(
    argv: list[str],
    work_ro_binds: list[tuple[pathlib.Path, str]],
) -> list[str]:
    """Insert `--ro-bind <host> <guest>` entries immediately after `--bind <ws> /work`.

    `ops.e1.sandbox.build_claude_worker_bwrap_argv` places `extra_ro_binds` *before*
    `--bind <ws> /work`, which would overmount files inside `/work`. Inserting right
    after `--bind <ws> /work` makes files like `/work/tests_spec.py` genuinely read-only
    and un-deletable (EROFS/EBUSY) inside `/work` without modifying `ops/e1/sandbox.py`.
    """
    if not work_ro_binds:
        return argv
    out = list(argv)
    insert_at: int | None = None
    for i in range(len(out) - 2):
        if out[i] == "--bind" and out[i + 2] == "/work":
            insert_at = i + 3
            break
    if insert_at is None:
        raise ValueError("Could not find `--bind <ws> /work` in bwrap argv")
    extra: list[str] = []
    for host_p, guest_p in work_ro_binds:
        extra += ["--ro-bind", str(host_p.resolve()), guest_p]
    out[insert_at:insert_at] = extra
    return out


def assert_fl_git_clean(plan_path: pathlib.Path) -> str:
    """Verify `ops/fl/`, `ops/e1/`, and `plan_path` are committed and clean in git. Returns HEAD sha."""
    rc_head, head = _git(["rev-parse", "HEAD"], REPO_ROOT)
    if rc_head != 0 or not head:
        raise SystemExit(f"Refusing to start: cannot get git HEAD ({head})")

    for code_dir in ("ops/fl", "ops/e1"):
        rc_code, dirty_code = _git(["status", "--porcelain", "--", code_dir], REPO_ROOT)
        if rc_code != 0 or dirty_code:
            raise SystemExit(f"Refusing to start: uncommitted changes in {code_dir}/:\n{dirty_code}")

    p_abs = plan_path.resolve()
    try:
        rel = p_abs.relative_to(REPO_ROOT.resolve())
    except ValueError:
        raise SystemExit(f"Refusing to start: plan {p_abs} is outside repo, cannot verify committed")

    rc_trk, _ = _git(["ls-files", "--error-unmatch", "--", str(rel)], REPO_ROOT)
    if rc_trk != 0:
        raise SystemExit(f"Refusing to start: plan {rel} is not tracked/committed in git")

    rc_plan, dirty_plan = _git(["status", "--porcelain", "--", str(rel)], REPO_ROOT)
    if rc_plan != 0 or dirty_plan:
        raise SystemExit(f"Refusing to start: plan {rel} has uncommitted changes:\n{dirty_plan}")

    return head


def load_fl_plan(plan_path: pathlib.Path) -> dict[str, Any]:
    raw = json.loads(plan_path.read_text(encoding="utf-8"))
    if raw.get("schema") != PLAN_SCHEMA:
        raise SystemExit(f"Plan schema must be {PLAN_SCHEMA}: {plan_path}")
    for req_k in ("id", "seed", "arms", "model"):
        if req_k not in raw:
            raise SystemExit(f"Plan missing required field {req_k!r}: {plan_path}")

    arms = list(raw["arms"])
    if not arms:
        raise SystemExit("Plan arms list must be non-empty")
    for arm in arms:
        if arm not in ARMS_FL:
            raise SystemExit(f"Unknown arm {arm!r}; valid arms: {ARMS_FL}")

    model_cfg = dict(raw["model"])
    agent = str(model_cfg.get("agent") or "claude")
    if agent != "claude":
        raise SystemExit(f"Unsupported model.agent={agent!r}; ops/fl currently supports 'claude'")
    model_cfg["agent"] = agent
    if not model_cfg.get("model"):
        raise SystemExit("Plan model.model is required (e.g. 'claude-haiku-5-5')")
    model_cfg["exam_model"] = str(model_cfg.get("exam_model") or model_cfg["model"])

    bank_s = raw.get("bank_path")
    bank_p = pathlib.Path(os.path.expandvars(os.path.expanduser(str(bank_s)))) if bank_s else DEFAULT_BANK_PATH
    if not bank_p.is_absolute():
        bank_p = (REPO_ROOT / bank_p).resolve()

    idx_s = raw.get("index_path")
    idx_p = pathlib.Path(os.path.expandvars(os.path.expanduser(str(idx_s)))) if idx_s else DEFAULT_INDEX_PATH
    if not idx_p.is_absolute():
        idx_p = (REPO_ROOT / idx_p).resolve()

    raw["_model"] = model_cfg
    raw["_bank_path"] = str(bank_p)
    raw["_index_path"] = str(idx_p)
    raw["_sha256"] = sha256_bytes(_canonical_json({k: v for k, v in raw.items() if not k.startswith("_")}))
    raw["_path"] = str(plan_path.resolve())
    return raw


def _sum_usage_entries(entries: list[dict[str, Any]]) -> dict[str, Any]:
    wall_s = 0.0
    tin = tout = calls = cache_c = cache_r = turns = 0
    cost_usd = 0.0
    any_usage = any_cache = any_cost = False
    infra_void = False

    for e in entries:
        wall_s += float(e.get("wall_s") or 0.0)
        if e.get("infra_error"):
            infra_void = True
        u = e.get("usage")
        if isinstance(u, dict):
            any_usage = True
            tin += int(u.get("input") or 0)
            tout += int(u.get("output") or 0)
            calls += int(u.get("calls") or 0)
            if "cache_creation_input_tokens" in u or "cache_read_input_tokens" in u:
                any_cache = True
                cache_c += int(u.get("cache_creation_input_tokens") or 0)
                cache_r += int(u.get("cache_read_input_tokens") or 0)
            if u.get("num_turns") is not None:
                turns += int(u.get("num_turns") or 0)
            if isinstance(u.get("cost_usd"), (int, float)):
                any_cost = True
                cost_usd += float(u["cost_usd"])
        elif isinstance(e.get("cost_usd"), (int, float)):
            any_cost = True
            cost_usd += float(e["cost_usd"])

    return {
        "wall_s": round(wall_s, 3),
        "calls": calls if any_usage else None,
        "tokens_in": tin if any_usage else None,
        "tokens_out": tout if any_usage else None,
        "cache_creation_input_tokens": cache_c if any_cache else None,
        "cache_read_input_tokens": cache_r if any_cache else None,
        "num_turns": turns if any_usage else None,
        "cost_usd": round(cost_usd, 6) if any_cost else None,
        "infra_void": infra_void,
    }


def _compute_attempt_confusion(attempts: list[dict[str, Any]]) -> dict[str, int]:
    tp = fp = tn = fn = n_gated = 0
    for a in attempts:
        gv = a.get("gate_verdict")
        ev = a.get("eval_verdict")
        if gv is None or ev is None:
            continue
        n_gated += 1
        if gv and ev:
            tp += 1
        elif gv and not ev:
            fp += 1
        elif (not gv) and (not ev):
            tn += 1
        else:
            fn += 1
    return {"tp": tp, "fp": fp, "tn": tn, "fn": fn, "n_gated": n_gated}


class FLRunner:
    """Fast-lane single-round code experiment runner."""

    def __init__(
        self,
        plan_path: pathlib.Path,
        root: pathlib.Path,
        *,
        calibrate_n: int | None = None,
        allow_uncommitted: bool = False,
        verify_bank_sha: bool = True,
    ) -> None:
        self.plan_path = plan_path.resolve()
        self.root = root.expanduser().resolve()
        self.calibrate_n = calibrate_n
        self.allow_uncommitted = allow_uncommitted
        self.plan = load_fl_plan(self.plan_path)

        if not self.allow_uncommitted:
            self.git_head = assert_fl_git_clean(self.plan_path)
        else:
            _, h = _git(["rev-parse", "HEAD"], REPO_ROOT)
            self.git_head = h or "unknown"

        self.seed = int(self.plan["seed"])
        self.bank_path = pathlib.Path(self.plan["_bank_path"])
        self.index_path = pathlib.Path(self.plan["_index_path"])

        if self.calibrate_n is not None:
            if self.calibrate_n <= 0:
                raise SystemExit(f"--calibrate N must be > 0, got {self.calibrate_n}")
            loaded = load_bank_tasks(
                self.bank_path,
                index_path=self.index_path,
                seed=self.seed,
                difficulties=["medium", "hard"],
                n_tasks=self.calibrate_n,
                verify_sha256=verify_bank_sha,
            )
            self.arms = ["B0"]
        else:
            loaded = load_bank_tasks(
                self.bank_path,
                index_path=self.index_path,
                seed=self.seed,
                task_ids=self.plan.get("task_ids"),
                difficulties=self.plan.get("difficulties"),
                n_tasks=self.plan.get("n_tasks"),
                verify_sha256=verify_bank_sha,
            )
            self.arms = list(self.plan["arms"])

        self.bank_sha256: str = loaded["bank_sha256"]
        self.tasks: list[dict[str, Any]] = loaded["tasks"]
        self.skipped_tasks: list[dict[str, Any]] = loaded["skipped"]
        if not self.tasks:
            raise SystemExit("No eligible tasks selected from bank")

        self.model_cfg = self.plan["_model"]
        self.worker_model: str = str(self.model_cfg["model"])
        self.exam_model: str = str(self.model_cfg["exam_model"])
        self.attempt_timeout_s = float(self.plan.get("attempt_timeout_s", 300))
        self.eval_timeout_s = float(self.plan.get("eval_timeout_s", 45))
        self.per_fn_timeout_s = float(self.plan.get("per_fn_timeout_s", 20))
        self.per_call_timeout_s = float(self.plan.get("per_call_timeout_s", 2.0))
        self.eval_mem_mb = int(self.plan.get("eval_mem_mb", 1024))
        self.max_attempts = int(self.plan.get("max_attempts", 3))
        self.mv_num_inputs = int(self.plan.get("mv_num_inputs", 20))
        self.jobs = max(1, int(self.plan.get("jobs", 1)))

        self.net_proxy: AllowlistUnixProxy | None = None
        self._claude_creds_tmp: tempfile.TemporaryDirectory[str] | None = None
        self.claude_creds_file: pathlib.Path | None = None
        self.results_path = self.root / "results.jsonl"

    def _log(self, msg: str) -> None:
        line = f"{utc_now_iso()} {msg}"
        with _LOCK:
            print(line, flush=True)
            with open(self.root / "runner.log", "a", encoding="utf-8") as fh:
                fh.write(line + "\n")

    def _append_result_jsonl(self, record: dict[str, Any]) -> None:
        with _LOCK:
            with open(self.results_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")

    def _init_root_and_check_resume(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        run_meta_p = self.root / "RUN.json"
        if run_meta_p.is_file():
            prev = json.loads(run_meta_p.read_text(encoding="utf-8"))
            if prev.get("plan_sha256") != self.plan["_sha256"]:
                raise SystemExit(
                    f"Refusing resume: existing plan_sha256 ({prev.get('plan_sha256')}) "
                    f"!= current ({self.plan['_sha256']})"
                )
            if prev.get("bank_sha256") != self.bank_sha256:
                raise SystemExit("Refusing resume: bank_sha256 mismatch with existing RUN.json")
            if prev.get("calibrate_n") != self.calibrate_n:
                raise SystemExit("Refusing resume: --calibrate mode mismatch with existing RUN.json")
        else:
            atomic_write_json(
                run_meta_p,
                {
                    "schema": RUN_SCHEMA,
                    "plan_id": self.plan["id"],
                    "plan_path": self.plan["_path"],
                    "plan_sha256": self.plan["_sha256"],
                    "bank_path": str(self.bank_path),
                    "bank_sha256": self.bank_sha256,
                    "seed": self.seed,
                    "git_head": self.git_head,
                    "agent": "claude",
                    "model": self.worker_model,
                    "exam_model": self.exam_model,
                    "calibrate_n": self.calibrate_n,
                    "arms": self.arms,
                    "n_tasks": len(self.tasks),
                    "task_ids": [t["task_id"] for t in self.tasks],
                    "skipped_tasks": self.skipped_tasks,
                    "created_utc": utc_now_iso(),
                },
            )

        for sk in self.skipped_tasks:
            self._log(f"skip_bank_task {sk['task_id']} ({sk['difficulty']}): {sk['reason']}")

        creds_src_s = self.model_cfg.get("credentials_path")
        creds_src = (
            pathlib.Path(os.path.expandvars(os.path.expanduser(str(creds_src_s))))
            if creds_src_s
            else None
        )
        self._claude_creds_tmp = tempfile.TemporaryDirectory(prefix="fl_claude_creds_")
        self.claude_creds_file = prepare_claude_credentials(
            pathlib.Path(self._claude_creds_tmp.name),
            src_creds_path=creds_src,
        )

    def _run_preflight_negative_controls(self) -> None:
        other_arm_canary = self.root / "_nc_other_arm_prev"
        other_arm_canary.mkdir(parents=True, exist_ok=True)
        (other_arm_canary / "canary.txt").write_text("other-arm-secret\n", encoding="utf-8")

        creds_src_s = self.model_cfg.get("credentials_path")
        creds_src = (
            pathlib.Path(os.path.expandvars(os.path.expanduser(str(creds_src_s))))
            if creds_src_s
            else None
        )
        claude_bin_s = self.model_cfg.get("claude_bin")
        rep = run_claude_negative_controls(
            hidden_tests_path=self.bank_path,
            eval_dir=self.root,
            other_arm_ws=other_arm_canary,
            credentials_src=creds_src,
            claude_bin_override=claude_bin_s,
        )
        atomic_write_json(self.root / "negative_controls.json", rep)
        if not rep.get("passed"):
            raise SystemExit(
                f"Refusing to start: Claude negative controls failed (see {self.root / 'negative_controls.json'}): "
                f"leaks={rep.get('leaks')} sanity={rep.get('sanity')} "
                f"net={rep.get('net')} eval_net={rep.get('eval_net_isolated')}"
            )
        self._log("preflight negative_controls (claude) PASS")

    def _run_claude_session(
        self,
        *,
        ws_dir: pathlib.Path,
        prompt: str,
        model_id: str,
        log_path: pathlib.Path,
        work_ro_binds: list[tuple[pathlib.Path, str]] | None = None,
        extra_env: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Run one Claude Code session inside E1's `--unshare-net` allowlist-proxy bwrap sandbox."""
        assert self.net_proxy is not None, "allowlist proxy must be running"
        assert self.claude_creds_file is not None, "credentials file must be prepared"

        cmd = build_claude_cli_argv(model_id, prompt)
        claude_bin_s = self.model_cfg.get("claude_bin")
        env_map: dict[str, str] = {}
        if self.model_cfg.get("fake_mode"):
            env_map["FL_FAKE_MODE"] = str(self.model_cfg["fake_mode"])
        if extra_env:
            env_map.update(extra_env)

        # Ensure mount-point placeholder files exist inside ws_dir for any /work/... ro-binds
        if work_ro_binds:
            for _, guest_p in work_ro_binds:
                if guest_p.startswith("/work/"):
                    rel = guest_p[len("/work/"):]
                    mp = ws_dir / rel
                    mp.parent.mkdir(parents=True, exist_ok=True)
                    if not mp.exists():
                        mp.write_text("", encoding="utf-8")

        argv = build_claude_worker_bwrap_argv(
            cmd,
            workspace_dir=ws_dir,
            proxy_sock_path=self.net_proxy.sock_path,
            credentials_file=self.claude_creds_file,
            claude_bin_override=claude_bin_s,
            extra_env=env_map or None,
        )
        if work_ro_binds:
            argv = insert_work_ro_binds(argv, work_ro_binds)

        res = run_sandboxed(argv, timeout_s=self.attempt_timeout_s, log_path=log_path)
        usage = usage_from_claude_log(log_path)
        is_infra = False
        if usage is None:
            is_infra = True
        elif usage["calls"] == 0 and (
            usage["errors"] > 0
            or res["rc"] != 0
            or (usage.get("final_error") and _INFRA_ERR_RE.search(usage["final_error"]))
        ):
            is_infra = True

        return {
            "model": model_id,
            "rc": res["rc"],
            "wall_s": res["wall_s"],
            "timed_out": res["timed_out"],
            "usage": usage,
            "cost_usd": usage.get("cost_usd") if isinstance(usage, dict) else None,
            "infra_error": is_infra,
        }

    def _eval_on_cases(self, sol_src: str, entry_point: str, cases: list[dict[str, Any]]) -> dict[str, Any]:
        return evaluate_solution_on_cases(
            sol_src,
            entry_point,
            cases,
            per_fn_timeout_s=self.per_fn_timeout_s,
            total_timeout_s=self.eval_timeout_s,
            mem_limit_mb=self.eval_mem_mb,
        )

    def _run_test_writer_session(
        self,
        *,
        task: dict[str, Any],
        cell_dir: pathlib.Path,
        model_id: str,
        role: str,
    ) -> dict[str, Any]:
        """Run a separate Claude session that writes `/work/tests_spec.py`, then freeze & parse it."""
        tw_dir = cell_dir / "test_writer"
        tw_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=f"fl_tw_{task['task_id']}_{role}_") as ws_tmp:
            ws_p = pathlib.Path(ws_tmp)
            wres = self._run_claude_session(
                ws_dir=ws_p,
                prompt=build_test_writer_prompt(task),
                model_id=model_id,
                log_path=tw_dir / "agent.log",
                extra_env={"FL_ROLE": role, "FL_TASK_ID": task["task_id"]},
            )
            spec_p = ws_p / "tests_spec.py"
            spec_text = spec_p.read_text(encoding="utf-8", errors="replace") if spec_p.is_file() else ""

        frozen_path = cell_dir / "frozen_tests_spec.py"
        frozen_sha = atomic_write_text(frozen_path, spec_text)
        cases, parse_err = parse_tests_spec_text(spec_text)
        atomic_write_json(
            cell_dir / "frozen_tests_meta.json",
            {
                "role": role,
                "model": model_id,
                "sha256": frozen_sha,
                "n_cases": len(cases),
                "parse_error": parse_err,
                "session": wres,
            },
        )
        return {
            "role": role,
            "frozen_path": frozen_path,
            "frozen_sha256": frozen_sha,
            "cases": cases,
            "parse_error": parse_err,
            "session": {"role": role, **wres, "frozen_sha256": frozen_sha, "n_cases": len(cases), "parse_error": parse_err},
        }

    def _run_input_gen_session(
        self,
        *,
        task: dict[str, Any],
        cell_dir: pathlib.Path,
        model_id: str,
    ) -> dict[str, Any]:
        """Run a separate Claude session that writes `/work/gen_inputs.py`, then run it in eval sandbox."""
        ig_dir = cell_dir / "input_gen"
        ig_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=f"fl_ig_{task['task_id']}_") as ws_tmp:
            ws_p = pathlib.Path(ws_tmp)
            wres = self._run_claude_session(
                ws_dir=ws_p,
                prompt=build_input_gen_prompt(task, n_inputs=self.mv_num_inputs),
                model_id=model_id,
                log_path=ig_dir / "agent.log",
                extra_env={"FL_ROLE": "mv_input_gen", "FL_TASK_ID": task["task_id"]},
            )
            gen_p = ws_p / "gen_inputs.py"
            gen_text = gen_p.read_text(encoding="utf-8", errors="replace") if gen_p.is_file() else ""

        gen_copy = cell_dir / "gen_inputs.py"
        gen_sha = atomic_write_text(gen_copy, gen_text)
        if gen_text.strip():
            gen_run = run_input_generator_in_sandbox(
                gen_text,
                max_inputs=self.mv_num_inputs,
                timeout_s=min(15.0, self.eval_timeout_s),
                mem_limit_mb=self.eval_mem_mb,
            )
        else:
            gen_run = {"ok": False, "inputs": [], "error": "missing_gen_inputs_py", "wall_s": 0.0}

        # Combine generated inputs + visible_tests' args ONLY (no expected outputs)
        vis_encoded = [encode_val_host(c["args"]) for c in task["visible_tests"]]
        combined_inputs = deduplicate_encoded_inputs(list(gen_run.get("inputs") or []) + vis_encoded)

        meta = {
            "role": "mv_input_gen",
            "model": model_id,
            "gen_sha256": gen_sha,
            "n_generated_inputs": len(gen_run.get("inputs") or []),
            "n_visible_arg_inputs": len(vis_encoded),
            "n_total_inputs": len(combined_inputs),
            "gen_error": gen_run.get("error"),
            "inputs": combined_inputs,
            "session": {"role": "mv_input_gen", **wres},
        }
        atomic_write_json(cell_dir / "mv_inputs.json", meta)
        return meta

    def _run_single_coding_attempt(
        self,
        *,
        task: dict[str, Any],
        arm: str,
        att: int,
        att_dir: pathlib.Path,
        prompt: str,
        prev_ws_dir: pathlib.Path | None = None,
        work_ro_binds: list[tuple[pathlib.Path, str]] | None = None,
    ) -> tuple[dict[str, Any], str, pathlib.Path | None]:
        """Run one coding attempt in a fresh (or carried for B0x3) workspace.

        If `arm == "B0x3"`, persists a copy of the post-attempt workspace in `att_dir / "ws_after"`
        so the next attempt can start from it.
        """
        att_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=f"fl_ws_{task['task_id']}_{arm}_a{att}_") as ws_tmp:
            ws_p = pathlib.Path(ws_tmp)
            if prev_ws_dir is not None and prev_ws_dir.is_dir():
                for item in prev_ws_dir.iterdir():
                    dst = ws_p / item.name
                    if item.is_dir():
                        shutil.copytree(item, dst)
                    else:
                        shutil.copy2(item, dst)

            wres = self._run_claude_session(
                ws_dir=ws_p,
                prompt=prompt,
                model_id=self.worker_model,
                log_path=att_dir / "agent.log",
                work_ro_binds=work_ro_binds,
                extra_env={"FL_ROLE": "coder", "FL_ARM": arm, "FL_ATTEMPT": str(att), "FL_TASK_ID": task["task_id"]},
            )
            sol_p = ws_p / "solution.py"
            cand_src = sol_p.read_text(encoding="utf-8", errors="replace") if sol_p.is_file() else ""
            cand_sha = atomic_write_text(att_dir / "candidate_solution.py", cand_src)

            next_ws_copy: pathlib.Path | None = None
            if arm == "B0x3":
                next_ws_copy = att_dir / "ws_after"
                if next_ws_copy.exists():
                    shutil.rmtree(next_ws_copy)
                shutil.copytree(ws_p, next_ws_copy)

        eval_res = self._eval_on_cases(cand_src, task["entry_point"], task["eval_hidden"])
        att_entry = {
            "attempt": att,
            **wres,
            "candidate_sha256": cand_sha,
            "gate_verdict": None,
            "gate_detail": None,
            "eval_verdict": bool(eval_res["passed"]),
            "eval_detail": eval_res,
        }
        return att_entry, cand_src, next_ws_copy

    def _run_task_arm(self, task: dict[str, Any], arm: str) -> dict[str, Any]:
        tid = task["task_id"]
        ep = task["entry_point"]
        cell_dir = self.root / "cells" / tid / arm
        done_p = cell_dir / "done.json"
        rec_p = cell_dir / "record.json"

        if done_p.is_file() and rec_p.is_file():
            return json.loads(rec_p.read_text(encoding="utf-8"))

        cell_dir.mkdir(parents=True, exist_ok=True)
        base_prompt = build_task_prompt(task)

        attempts_meta: list[dict[str, Any]] = []
        cand_sources: list[str] = []
        extra_sessions: list[dict[str, Any]] = []
        reused_cost_entries: list[dict[str, Any]] = []
        reused_from: dict[str, bool] = {}

        delivered_idx = 0
        gate_passed: bool | None = None
        undetermined = False
        undetermined_reason: str | None = None
        judge_meta: dict[str, Any] = {}

        # ── B0: 1 attempt, deliver it ────────────────────────────────────────
        if arm == "B0":
            att_e, cand_src, _ = self._run_single_coding_attempt(
                task=task, arm=arm, att=1, att_dir=cell_dir / "attempt_1", prompt=base_prompt
            )
            attempts_meta.append(att_e)
            cand_sources.append(cand_src)
            delivered_idx = 0

        # ── B0x3: 3 sequential attempts carrying workspace, deliver last ─────
        elif arm == "B0x3":
            prev_ws: pathlib.Path | None = None
            for att in range(1, self.max_attempts + 1):
                prompt = base_prompt if att == 1 else build_b0x3_retry_prompt(task)
                att_e, cand_src, prev_ws = self._run_single_coding_attempt(
                    task=task,
                    arm=arm,
                    att=att,
                    att_dir=cell_dir / f"attempt_{att}",
                    prompt=prompt,
                    prev_ws_dir=prev_ws,
                )
                attempts_meta.append(att_e)
                cand_sources.append(cand_src)
            delivered_idx = len(attempts_meta) - 1

        # ── GT / EX: fresh attempts gated on gate_hidden or visible_tests ────
        elif arm in ("GT", "EX"):
            gate_cases = task["gate_hidden"] if arm == "GT" else task["visible_tests"]
            for att in range(1, self.max_attempts + 1):
                att_e, cand_src, _ = self._run_single_coding_attempt(
                    task=task, arm=arm, att=att, att_dir=cell_dir / f"attempt_{att}", prompt=base_prompt
                )
                g_res = self._eval_on_cases(cand_src, ep, gate_cases)
                g_ok = bool(g_res["passed"])
                att_e["gate_verdict"] = g_ok
                att_e["gate_detail"] = g_res
                attempts_meta.append(att_e)
                cand_sources.append(cand_src)
                delivered_idx = att - 1
                if g_ok:
                    gate_passed = True
                    break
                gate_passed = False

        # ── TF / XM: test-writer session + frozen tests gate ─────────────────
        elif arm in ("TF", "XM"):
            tw_model = self.worker_model if arm == "TF" else self.exam_model
            tw = self._run_test_writer_session(
                task=task,
                cell_dir=cell_dir,
                model_id=tw_model,
                role="tf_test_writer" if arm == "TF" else "xm_exam_writer",
            )
            extra_sessions.append(tw["session"])
            judge_meta = {
                "frozen_tests_sha256": tw["frozen_sha256"],
                "n_generated_tests": len(tw["cases"]),
                "parse_error": tw["parse_error"],
                "test_writer_model": tw_model,
            }
            if not tw["cases"]:
                undetermined = True
                undetermined_reason = tw["parse_error"] or "zero_cases"
                gate_passed = None
                att_e, cand_src, _ = self._run_single_coding_attempt(
                    task=task, arm=arm, att=1, att_dir=cell_dir / "attempt_1", prompt=base_prompt
                )
                attempts_meta.append(att_e)
                cand_sources.append(cand_src)
                delivered_idx = 0
            else:
                work_ro = [(tw["frozen_path"], "/work/tests_spec.py")] if arm == "TF" else None
                coder_prompt = build_tf_coder_prompt(task) if arm == "TF" else base_prompt
                for att in range(1, self.max_attempts + 1):
                    att_e, cand_src, _ = self._run_single_coding_attempt(
                        task=task,
                        arm=arm,
                        att=att,
                        att_dir=cell_dir / f"attempt_{att}",
                        prompt=coder_prompt,
                        work_ro_binds=work_ro,
                    )
                    # Always gate using the host's frozen copy
                    g_res = self._eval_on_cases(cand_src, ep, tw["cases"])
                    g_ok = bool(g_res["passed"])
                    att_e["gate_verdict"] = g_ok
                    att_e["gate_detail"] = g_res
                    attempts_meta.append(att_e)
                    cand_sources.append(cand_src)
                    delivered_idx = att - 1
                    if g_ok:
                        gate_passed = True
                        break
                    gate_passed = False

        # ── MV: 3 fresh attempts + gen_inputs.py + output clustering ─────────
        elif arm == "MV":
            ig_meta = self._run_input_gen_session(task=task, cell_dir=cell_dir, model_id=self.exam_model)
            extra_sessions.append(ig_meta["session"])
            mv_inputs = ig_meta["inputs"]

            output_tags: list[list[str]] = []
            output_details: list[dict[str, Any]] = []
            for att in range(1, self.max_attempts + 1):
                att_e, cand_src, _ = self._run_single_coding_attempt(
                    task=task, arm=arm, att=att, att_dir=cell_dir / f"attempt_{att}", prompt=base_prompt
                )
                out_res = collect_outputs_in_sandbox(
                    cand_src,
                    ep,
                    mv_inputs,
                    per_call_timeout_s=self.per_call_timeout_s,
                    total_timeout_s=self.eval_timeout_s,
                    mem_limit_mb=self.eval_mem_mb,
                )
                output_tags.append(out_res["tags"])
                output_details.append({"load_error": out_res["load_error"], "wall_s": out_res["wall_s"]})
                attempts_meta.append(att_e)
                cand_sources.append(cand_src)

            mv_res = cluster_mv_outputs(output_tags)
            undetermined = bool(mv_res["undetermined"])
            delivered_idx = int(mv_res["delivered_idx"])
            if undetermined:
                undetermined_reason = "no_inputs" if not mv_inputs else "no_cluster_ge_2"
                gate_passed = None
            else:
                gate_passed = True
                for i, att_e in enumerate(attempts_meta):
                    att_e["gate_verdict"] = (i == delivered_idx)
                    att_e["gate_detail"] = {
                        "agree_count": mv_res["agree_counts"][i],
                        "in_winning_cluster": i in mv_res["winning_cluster"],
                        "load_error": output_details[i]["load_error"],
                    }
            judge_meta = {
                "n_inputs": len(mv_inputs),
                "n_generated_inputs": ig_meta["n_generated_inputs"],
                "n_visible_arg_inputs": ig_meta["n_visible_arg_inputs"],
                "gen_error": ig_meta["gen_error"],
                "clusters": mv_res["clusters"],
                "largest_cluster_size": mv_res["largest_cluster_size"],
                "winning_cluster": mv_res["winning_cluster"],
                "agree_counts": mv_res["agree_counts"],
            }
            atomic_write_json(
                cell_dir / "mv_outputs.json",
                {"inputs": mv_inputs, "output_tags": output_tags, "mv": mv_res},
            )

        # ── CT: reuse MV's 3 solutions + inputs and XM's generated tests ─────
        elif arm == "CT":
            mv_dir = self.root / "cells" / tid / "MV"
            xm_dir = self.root / "cells" / tid / "XM"

            # 1) Reuse MV's 3 solutions + inputs if MV already completed for this task
            if (mv_dir / "done.json").is_file() and (mv_dir / "mv_outputs.json").is_file() and (mv_dir / "record.json").is_file():
                reused_from["mv"] = True
                mv_rec = json.loads((mv_dir / "record.json").read_text(encoding="utf-8"))
                mv_out = json.loads((mv_dir / "mv_outputs.json").read_text(encoding="utf-8"))
                mv_inputs = mv_out["inputs"]
                output_tags = mv_out["output_tags"]
                for att in range(1, self.max_attempts + 1):
                    src_p = mv_dir / f"attempt_{att}" / "candidate_solution.py"
                    cand_src = src_p.read_text(encoding="utf-8", errors="replace") if src_p.is_file() else ""
                    cand_sources.append(cand_src)
                    prev_a = mv_rec["attempts"][att - 1]
                    att_copy = {
                        "attempt": att,
                        "model": prev_a.get("model"),
                        "rc": prev_a.get("rc"),
                        "wall_s": prev_a.get("wall_s"),
                        "timed_out": prev_a.get("timed_out"),
                        "usage": prev_a.get("usage"),
                        "cost_usd": prev_a.get("cost_usd"),
                        "infra_error": prev_a.get("infra_error"),
                        "candidate_sha256": prev_a.get("candidate_sha256"),
                        "reused_from_mv": True,
                        "gate_verdict": None,
                        "gate_detail": None,
                        "eval_verdict": prev_a.get("eval_verdict"),
                        "eval_detail": prev_a.get("eval_detail"),
                    }
                    attempts_meta.append(att_copy)
                    reused_cost_entries.append(prev_a)
                for ex_s in mv_rec.get("extra_sessions") or []:
                    reused_cost_entries.append(ex_s)
            else:
                reused_from["mv"] = False
                ig_meta = self._run_input_gen_session(task=task, cell_dir=cell_dir, model_id=self.exam_model)
                extra_sessions.append(ig_meta["session"])
                mv_inputs = ig_meta["inputs"]
                output_tags = []
                for att in range(1, self.max_attempts + 1):
                    att_e, cand_src, _ = self._run_single_coding_attempt(
                        task=task, arm=arm, att=att, att_dir=cell_dir / f"attempt_{att}", prompt=base_prompt
                    )
                    out_res = collect_outputs_in_sandbox(
                        cand_src,
                        ep,
                        mv_inputs,
                        per_call_timeout_s=self.per_call_timeout_s,
                        total_timeout_s=self.eval_timeout_s,
                        mem_limit_mb=self.eval_mem_mb,
                    )
                    output_tags.append(out_res["tags"])
                    attempts_meta.append(att_e)
                    cand_sources.append(cand_src)

            # 2) Reuse XM's generated tests if XM already completed for this task
            if (xm_dir / "done.json").is_file() and (xm_dir / "frozen_tests_spec.py").is_file() and (xm_dir / "record.json").is_file():
                reused_from["xm"] = True
                xm_rec = json.loads((xm_dir / "record.json").read_text(encoding="utf-8"))
                xm_spec_text = (xm_dir / "frozen_tests_spec.py").read_text(encoding="utf-8", errors="replace")
                xm_cases, xm_parse_err = parse_tests_spec_text(xm_spec_text)
                for ex_s in xm_rec.get("extra_sessions") or []:
                    reused_cost_entries.append(ex_s)
            else:
                reused_from["xm"] = False
                tw = self._run_test_writer_session(
                    task=task, cell_dir=cell_dir, model_id=self.exam_model, role="ct_exam_writer"
                )
                extra_sessions.append(tw["session"])
                xm_cases = tw["cases"]
                xm_parse_err = tw["parse_error"]

            # 3) Score each solution on XM tests + MV agreement
            tests_passed_list: list[int] = []
            for cand_src in cand_sources:
                if xm_cases:
                    t_ev = self._eval_on_cases(cand_src, ep, xm_cases)
                    tests_passed_list.append(int(t_ev["n_passed"]))
                else:
                    tests_passed_list.append(0)

            ct_res = score_ct_solutions(output_tags, tests_passed_list, len(xm_cases))
            undetermined = bool(ct_res["undetermined"])
            delivered_idx = int(ct_res["delivered_idx"])
            if undetermined:
                if not xm_cases:
                    undetermined_reason = xm_parse_err or "zero_generated_tests"
                else:
                    undetermined_reason = "all_ct_scores_zero"
                gate_passed = None
            else:
                gate_passed = True
                for i, att_e in enumerate(attempts_meta):
                    att_e["gate_verdict"] = (i == delivered_idx)
                    att_e["gate_detail"] = {
                        "ct_score": ct_res["scores"][i],
                        "agree_count": ct_res["agree_counts"][i],
                        "tests_passed": ct_res["tests_passed"][i],
                        "n_generated_tests": len(xm_cases),
                    }
            judge_meta = {
                "reused_from": reused_from,
                "n_inputs": len(mv_inputs),
                "n_generated_tests": len(xm_cases),
                "xm_parse_error": xm_parse_err,
                "scores": ct_res["scores"],
                "agree_counts": ct_res["agree_counts"],
                "tests_passed": ct_res["tests_passed"],
                "clusters": ct_res["clusters"],
                "tie": ct_res["tie"],
            }
            atomic_write_json(cell_dir / "ct_scores.json", judge_meta)

        else:
            raise ValueError(f"Unsupported arm: {arm!r}")

        # Persist delivered solution & compute final confusion metrics
        delivered_src = cand_sources[delivered_idx]
        delivered_sha = atomic_write_text(cell_dir / "delivered_solution.py", delivered_src)
        delivered_att = attempts_meta[delivered_idx]
        delivered_correct = bool(delivered_att["eval_verdict"])

        # Task-level judge confusion vs truth
        false_accept = bool((not undetermined) and (gate_passed is True) and (not delivered_correct))
        if arm in ("GT", "EX", "TF", "XM"):
            false_reject = any(
                (a.get("gate_verdict") is False) and bool(a.get("eval_verdict"))
                for a in attempts_meta
            )
        elif arm in ("MV", "CT"):
            false_reject = bool((not delivered_correct) and any(bool(a.get("eval_verdict")) for a in attempts_meta))
        else:
            false_reject = False

        att_conf = _compute_attempt_confusion(attempts_meta)

        # Standalone cost (full cost of running this arm) vs incremental API cost actually spent by this cell
        if arm == "CT" and (reused_from.get("mv") or reused_from.get("xm")):
            own_entries: list[dict[str, Any]] = []
            if not reused_from.get("mv"):
                own_entries.extend(attempts_meta)
            own_entries.extend(extra_sessions)
            inc_totals = _sum_usage_entries(own_entries)
            full_totals = _sum_usage_entries(own_entries + reused_cost_entries)
            if not own_entries and full_totals["cost_usd"] is not None:
                inc_totals["cost_usd"] = 0.0
        else:
            full_totals = _sum_usage_entries(attempts_meta + extra_sessions)
            inc_totals = full_totals

        record: dict[str, Any] = {
            "schema": RESULT_SCHEMA,
            "ts_utc": utc_now_iso(),
            "plan_id": self.plan["id"],
            "task_id": tid,
            "difficulty": task["difficulty"],
            "entry_point": ep,
            "arm": arm,
            "model": self.worker_model,
            "exam_model": self.exam_model,
            "n_visible_tests": len(task["visible_tests"]),
            "n_gate_hidden": len(task["gate_hidden"]),
            "n_eval_hidden": len(task["eval_hidden"]),
            "attempts_count": len(attempts_meta),
            "delivered_attempt": delivered_idx + 1,
            "delivered_sha256": delivered_sha,
            "delivered_correct": delivered_correct,
            "delivered_eval": delivered_att["eval_detail"],
            "gate_passed": gate_passed,
            "undetermined": undetermined,
            "undetermined_reason": undetermined_reason,
            "false_accept": false_accept,
            "false_reject": false_reject,
            "attempt_confusion": att_conf,
            "attempts": attempts_meta,
            "extra_sessions": extra_sessions,
            "judge_meta": judge_meta,
            "reused_from": reused_from or None,
            "wall_s": full_totals["wall_s"],
            "incremental_wall_s": inc_totals["wall_s"],
            "calls": full_totals["calls"],
            "tokens_in": full_totals["tokens_in"],
            "tokens_out": full_totals["tokens_out"],
            "cache_creation_input_tokens": full_totals["cache_creation_input_tokens"],
            "cache_read_input_tokens": full_totals["cache_read_input_tokens"],
            "num_turns": full_totals["num_turns"],
            "cost_usd": full_totals["cost_usd"],
            "incremental_cost_usd": inc_totals["cost_usd"],
            "infra_void": full_totals["infra_void"],
        }

        atomic_write_json(rec_p, record)
        atomic_write_json(
            done_p,
            {
                "done": True,
                "ts_utc": utc_now_iso(),
                "delivered_attempt": delivered_idx + 1,
                "delivered_correct": delivered_correct,
                "delivered_sha256": delivered_sha,
            },
        )
        self._append_result_jsonl(record)
        self._log(
            f"{tid}({task['difficulty']})/{arm} correct={delivered_correct} "
            f"gate={gate_passed} undet={undetermined} fa={false_accept} fr={false_reject} "
            f"att={len(attempts_meta)} deliv={delivered_idx + 1} "
            f"cost=${record['incremental_cost_usd']} wall={record['wall_s']}s"
        )
        return record

    def _run_one_task(self, task: dict[str, Any]) -> list[dict[str, Any]]:
        # Ensure MV and XM run before CT if present in plan so CT can reuse them cleanly
        ordered_arms = [a for a in self.arms if a != "CT"] + ([a for a in self.arms if a == "CT"])
        out: list[dict[str, Any]] = []
        for arm in ordered_arms:
            out.append(self._run_task_arm(task, arm))
        return out

    def run(self) -> dict[str, Any]:
        self._init_root_and_check_resume()
        records: list[dict[str, Any]] = []
        try:
            self._run_preflight_negative_controls()

            allowed_connect = _parse_allowed_connect_hosts(self.model_cfg.get("allowed_connect_hosts"))
            self.net_proxy = AllowlistUnixProxy(
                allowed_connect=allowed_connect,
                source_server_port=None,
                log_path=self.root / "proxy.jsonl",
            )
            self.net_proxy.start()
            self._log(
                f"allowlist_proxy listening on {self.net_proxy.sock_path} "
                f"connect={sorted(self.net_proxy.allowed_connect)}"
            )

            if self.jobs == 1 or len(self.tasks) == 1:
                for t in self.tasks:
                    records.extend(self._run_one_task(t))
            else:
                with concurrent.futures.ThreadPoolExecutor(max_workers=self.jobs) as ex:
                    futs = [ex.submit(self._run_one_task, t) for t in self.tasks]
                    for fut in concurrent.futures.as_completed(futs):
                        records.extend(fut.result())
        finally:
            if self.net_proxy is not None:
                self.net_proxy.stop()
                self.net_proxy = None
            if self._claude_creds_tmp is not None:
                self._claude_creds_tmp.cleanup()
                self._claude_creds_tmp = None
                self.claude_creds_file = None
            kill_all_live()

        summary: dict[str, Any] = {
            "root": str(self.root),
            "results_jsonl": str(self.results_path),
            "bank_sha256": self.bank_sha256,
            "n_tasks": len(self.tasks),
            "n_skipped": len(self.skipped_tasks),
            "arms": self.arms,
        }
        if self.calibrate_n is not None:
            by_diff: dict[str, dict[str, Any]] = {}
            valid_recs = [r for r in records if not r.get("infra_void")]
            for diff in ("medium", "hard"):
                sub = [r for r in valid_recs if r.get("difficulty") == diff]
                ok = sum(1 for r in sub if r.get("delivered_correct"))
                by_diff[diff] = {
                    "passed": ok,
                    "total": len(sub),
                    "rate": round(ok / len(sub), 4) if sub else None,
                }
            tot_ok = sum(1 for r in valid_recs if r.get("delivered_correct"))
            summary["calibrate"] = {
                "n_requested": self.calibrate_n,
                "n_valid": len(valid_recs),
                "n_infra_void": len(records) - len(valid_recs),
                "overall": {
                    "passed": tot_ok,
                    "total": len(valid_recs),
                    "rate": round(tot_ok / len(valid_recs), 4) if valid_recs else None,
                },
                "by_difficulty": by_diff,
            }
        return summary


def main() -> int:
    ap = argparse.ArgumentParser(description="Fast-lane single-round code runner (Claude Haiku + zero-answer judges)")
    ap.add_argument("--plan", type=pathlib.Path, required=True, help="Committed plan JSON path")
    ap.add_argument("--root", type=pathlib.Path, required=True, help="Output directory ROOT")
    ap.add_argument(
        "--calibrate",
        type=int,
        default=None,
        metavar="N",
        help="Calibration mode: run only B0 on N tasks sampled with plan seed from medium+hard",
    )
    args = ap.parse_args()

    runner = FLRunner(args.plan, args.root, calibrate_n=args.calibrate)
    out = runner.run()
    if args.calibrate is not None and "calibrate" in out:
        cal = out["calibrate"]
        print("\n=== Calibration Pass Rate (B0) ===")
        for diff, st in cal["by_difficulty"].items():
            print(f"  {diff:8s}: {st['passed']}/{st['total']} ({st['rate']})")
        ov = cal["overall"]
        print(f"  {'overall':8s}: {ov['passed']}/{ov['total']} ({ov['rate']})")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
