#!/usr/bin/env python3
"""ops.fl.run_fl — Fast-lane single-round code experiment runner (B0/B0x3/GT/EX/TF/XM/XMH/XMVH/MV/CT).

Supports both local `pi` workers (e.g. qwen/qwen3.5-9b via LM Studio) and Claude Code workers,
with a separate configurable `exam` agent (e.g. Claude Haiku) for XMH/XMVH exams and MV input
generation. Reuses `ops.e1` sandboxes, allowlist proxy, usage parsers, and negative controls
directly by import.

Usage:
  python3 ops/fl/run_fl.py --plan ops/fl/plans/PLAN.json --root /tmp/fl_run [--calibrate N]
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import pathlib
import re
import shutil
import sys
import tempfile
import threading
import time
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from ops.e1.negative_controls import run_claude_negative_controls, run_negative_controls
from ops.e1.netproxy import AllowlistUnixProxy
from ops.e1.run_e1 import (
    _INFRA_ERR_RE,
    _canonical_json,
    _git,
    _parse_allowed_connect_hosts,
    build_claude_cli_argv,
    usage_from_claude_log,
    usage_from_pi_log,
)
from ops.e1.sandbox import (
    build_claude_worker_bwrap_argv,
    build_worker_bwrap_argv,
    kill_all_live,
    prepare_claude_credentials,
    prepare_sanitized_pi_cfg,
    run_sandboxed,
)
from ops.fl import (
    ARMS_FL,
    DEFAULT_BANK_PATH,
    DEFAULT_INDEX_PATH,
    DEFAULT_PI_CFG_DIR,
    GATED_RETRY_ARMS,
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
from ops.fl.bank import GT_SOURCES, TASK_FORMATS, is_evalplus_bank_dir, load_bank_tasks, parse_tests_spec_text
from ops.fl.eval_fl import (
    cluster_mv_outputs,
    collect_outputs_in_sandbox,
    collect_stdio_outputs_in_sandbox,
    deduplicate_encoded_inputs,
    deduplicate_stdio_inputs,
    encode_val_host,
    evaluate_solution_on_cases,
    evaluate_stdio_on_cases,
    run_input_generator_in_sandbox,
    run_stdio_input_generator_in_sandbox,
    score_ct_solutions,
    self_check_xmvh_exam,
)

_LOCK = threading.Lock()
_EXAM_CACHE_LOCK = threading.Lock()

_EXAM_USING_ARMS = frozenset({"XM", "XMH", "XMVH", "MV", "CT"})

_AUTH_ERR_RE = re.compile(
    r"OAuth token revoked|Failed to authenticate|authentication_error|invalid_api_key|\b401\b",
    re.I,
)

FEEDBACK_PREFIX = "Your previous solution failed on this input:\n"
FEEDBACK_MAX_BYTES = 400

# Harness-authored prompt suffixes (validated against KS-1)
_TASK_SUFFIX_FMT = "Write the function `{entry_point}` in /work/solution.py."
_STDIO_TASK_SUFFIX = (
    "Write a Python 3 program in /work/solution.py that reads from standard input and writes to standard output."
)
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
_STDIO_TEST_WRITER_SUFFIX = (
    "Do NOT write a solution or /work/solution.py. "
    "Write ONLY `/work/tests_spec.py` containing a single Python literal list of 5 to 15 test cases "
    "(covering statement examples, typical inputs, and edge cases). "
    "Format: a Python list of dicts, each with keys `'input'` (string passed to standard input) "
    "and `'output'` (exact expected standard output string), for example:\n"
    "[\n"
    "    {\"input\": \"...\\n\", \"output\": \"...\"},\n"
    "]\n"
    "Use ONLY Python literals (no imports, no function definitions, no function calls, no executable code)."
)
_EXAM_WRITER_SUFFIX_FMT = (
    "Do NOT write a solution or /work/solution.py. "
    "Write ONLY `/work/tests_spec.py` containing a single Python literal list of 5 to 15 test cases "
    "for `{entry_point}`. You MUST include every example input from the problem statement with your "
    "computed expected output, plus additional typical and edge cases. "
    "Format: a Python list of dicts, each with keys `'args'` (list of positional arguments passed as "
    "`{entry_point}(*args)`) and `'expected'` (exact expected return value), for example:\n"
    "[\n"
    "    {{\"args\": [...], \"expected\": ...}},\n"
    "]\n"
    "Use ONLY Python literals (no imports, no function definitions, no function calls, no executable code)."
)
_STDIO_EXAM_WRITER_SUFFIX = (
    "Do NOT write a solution or /work/solution.py. "
    "Write ONLY `/work/tests_spec.py` containing a single Python literal list of 5 to 15 test cases. "
    "You MUST include every example input from the problem statement with your computed expected output, "
    "plus additional typical and edge cases. "
    "Format: a Python list of dicts, each with keys `'input'` (string passed to standard input) "
    "and `'output'` (exact expected standard output string), for example:\n"
    "[\n"
    "    {\"input\": \"...\\n\", \"output\": \"...\"},\n"
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
_STDIO_INPUT_GEN_SUFFIX_FMT = (
    "Do NOT write a solution and do NOT compute expected outputs. "
    "Write ONLY `/work/gen_inputs.py` defining a function `gen_inputs()` that returns a list of {n_inputs} "
    "diverse, valid standard-input strings (covering small, edge, and typical inputs "
    "within the problem constraints; keep each input small enough to run quickly). "
    "Each element of the returned list MUST be a Python `str` containing the complete stdin for one test case. "
    "Use only the Python standard library and deterministic generation (fixed random seed if using random)."
)

# Verify harness-authored templates are KS-1 clean at import time (never check bank statement text)
for _tmpl in (
    FEEDBACK_PREFIX,
    _TASK_SUFFIX_FMT.format(entry_point="fn"),
    _STDIO_TASK_SUFFIX,
    _B0X3_RETRY_SUFFIX,
    _TF_RO_SPEC_NOTE,
    _TEST_WRITER_SUFFIX_FMT.format(entry_point="fn"),
    _STDIO_TEST_WRITER_SUFFIX,
    _EXAM_WRITER_SUFFIX_FMT.format(entry_point="fn"),
    _STDIO_EXAM_WRITER_SUFFIX,
    _INPUT_GEN_SUFFIX_FMT.format(entry_point="fn", n_inputs=20),
    _STDIO_INPUT_GEN_SUFFIX_FMT.format(n_inputs=20),
):
    assert_ks1_clean(_tmpl)


def build_task_prompt(task: dict[str, Any]) -> str:
    """Identical base task text across all arms."""
    # KS-1 checks only harness-authored templates (validated at import time above),
    # never bank problem statements or bank function names.
    if task.get("task_format") == "stdio":
        suffix = _STDIO_TASK_SUFFIX
    else:
        suffix = _TASK_SUFFIX_FMT.format(entry_point=task["entry_point"])
    return f"{task['prompt'].rstrip()}\n\n{suffix}"


def build_b0x3_retry_prompt(task: dict[str, Any]) -> str:
    assert_ks1_clean(_B0X3_RETRY_SUFFIX)
    return f"{build_task_prompt(task)}\n\n{_B0X3_RETRY_SUFFIX}"


def build_tf_coder_prompt(task: dict[str, Any]) -> str:
    assert_ks1_clean(_TF_RO_SPEC_NOTE)
    return f"{build_task_prompt(task)}\n\n{_TF_RO_SPEC_NOTE}"


def build_test_writer_prompt(task: dict[str, Any]) -> str:
    if task.get("task_format") == "stdio":
        suffix = _STDIO_TEST_WRITER_SUFFIX
    else:
        suffix = _TEST_WRITER_SUFFIX_FMT.format(entry_point=task["entry_point"])
    return f"{task['prompt'].rstrip()}\n\n{suffix}"


def build_exam_writer_prompt(task: dict[str, Any]) -> str:
    if task.get("task_format") == "stdio":
        suffix = _STDIO_EXAM_WRITER_SUFFIX
    else:
        suffix = _EXAM_WRITER_SUFFIX_FMT.format(entry_point=task["entry_point"])
    return f"{task['prompt'].rstrip()}\n\n{suffix}"


def build_input_gen_prompt(task: dict[str, Any], *, n_inputs: int = 20) -> str:
    if task.get("task_format") == "stdio":
        suffix = _STDIO_INPUT_GEN_SUFFIX_FMT.format(n_inputs=n_inputs)
    else:
        suffix = _INPUT_GEN_SUFFIX_FMT.format(entry_point=task["entry_point"], n_inputs=n_inputs)
    return f"{task['prompt'].rstrip()}\n\n{suffix}"


def build_retry_feedback(
    task: dict[str, Any],
    gate_cases: list[dict[str, Any]],
    gate_res: dict[str, Any],
) -> str:
    """Build retry feedback containing ONLY the single first failing input (never expected output), <= 400 UTF-8 bytes."""
    if not gate_cases:
        return ""
    idx = gate_res.get("first_failed_idx")
    if not isinstance(idx, int) or idx < 0 or idx >= len(gate_cases):
        idx = 0
    case = gate_cases[idx]
    if task.get("task_format") == "stdio":
        inp_text = str(case["input"])
    else:
        ep = task.get("entry_point")
        args = case["args"]
        if ep:
            inp_text = f"{ep}({', '.join(repr(a) for a in args)})"
        else:
            inp_text = repr(args)

    full = FEEDBACK_PREFIX + inp_text
    raw = full.encode("utf-8")
    if len(raw) <= FEEDBACK_MAX_BYTES:
        return full
    ellipsis = "...[truncated]"
    budget = FEEDBACK_MAX_BYTES - len(ellipsis.encode("utf-8"))
    trimmed = raw[:budget].decode("utf-8", errors="ignore")
    return trimmed + ellipsis


def _is_claude_auth_error(usage: dict[str, Any] | None, log_path: pathlib.Path, rc: int | None) -> bool:
    """Detect Claude OAuth / 401 authentication errors from parsed usage or raw session log."""
    final_err = str((usage or {}).get("final_error") or "")
    if final_err and _AUTH_ERR_RE.search(final_err):
        return True
    try:
        log_text = log_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        log_text = ""
    if not log_text:
        return False
    if usage is None or int(usage.get("calls") or 0) == 0:
        return bool(_AUTH_ERR_RE.search(log_text))
    if (rc not in (0, None) or int(usage.get("errors") or 0) > 0) and _AUTH_ERR_RE.search(log_text):
        return True
    return False


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
    agent = str(model_cfg.get("agent") or "claude").strip().lower()
    if agent not in ("claude", "pi"):
        raise SystemExit(f"Unsupported model.agent={agent!r}; valid: 'claude', 'pi'")
    model_cfg["agent"] = agent
    if agent == "claude":
        if not model_cfg.get("model"):
            raise SystemExit("Plan model.model is required for agent='claude' (e.g. 'claude-haiku-5-5')")
    else:
        providers = list(model_cfg.get("providers") or [])
        if not providers and model_cfg.get("provider"):
            providers = [str(model_cfg["provider"])]
        if not providers and not model_cfg.get("fake_agent"):
            raise SystemExit("Plan model.agent='pi' requires 'providers' (or 'provider' / 'fake_agent')")
        model_cfg["providers"] = providers
        model_cfg["model"] = str(model_cfg.get("model") or "qwen/qwen3.5-9b")

    if "exam" in raw and raw["exam"] is not None:
        exam_cfg = dict(raw["exam"])
        exam_agent = str(exam_cfg.get("agent") or "claude").strip().lower()
        if exam_agent not in ("claude", "pi"):
            raise SystemExit(f"Unsupported exam.agent={exam_agent!r}; valid: 'claude', 'pi'")
        exam_cfg["agent"] = exam_agent
        if not exam_cfg.get("model"):
            raise SystemExit("Plan exam.model is required (e.g. 'claude-haiku-5-5')")
        if exam_agent == "pi":
            eprovs = list(exam_cfg.get("providers") or [])
            if not eprovs and exam_cfg.get("provider"):
                eprovs = [str(exam_cfg["provider"])]
            exam_cfg["providers"] = eprovs
    elif agent == "claude":
        exam_cfg = dict(model_cfg)
        exam_cfg["model"] = str(model_cfg.get("exam_model") or model_cfg["model"])
    else:
        exam_cfg = {
            "agent": "claude",
            "model": str(model_cfg.get("exam_model") or "claude-haiku-5-5"),
        }
    model_cfg["exam_model"] = str(exam_cfg["model"])

    task_format = str(raw.get("task_format") or "function").strip().lower()
    if task_format not in TASK_FORMATS:
        raise SystemExit(f"Unsupported task_format={task_format!r}; valid formats: {TASK_FORMATS}")

    bank_s = raw.get("bank_path")
    bank_p = pathlib.Path(os.path.expandvars(os.path.expanduser(str(bank_s)))) if bank_s else DEFAULT_BANK_PATH
    if not bank_p.is_absolute():
        bank_p = (REPO_ROOT / bank_p).resolve()

    bank_type = str(raw.get("bank_type") or "").strip().lower() or (
        "evalplus" if is_evalplus_bank_dir(bank_p) else "jsonl"
    )
    if bank_type not in ("jsonl", "evalplus"):
        raise SystemExit(f"Unsupported bank_type={bank_type!r}; valid: 'jsonl', 'evalplus'")

    gt_source_raw = raw.get("gt_source")
    if gt_source_raw is None:
        gt_source = "visible" if bank_type == "evalplus" else "gate_hidden"
    else:
        gt_source = str(gt_source_raw).strip().lower()
    if gt_source not in GT_SOURCES:
        raise SystemExit(f"Unsupported gt_source={gt_source!r}; valid: {GT_SOURCES}")

    plan_bank_sha = raw.get("bank_sha256")
    if plan_bank_sha is not None:
        plan_bank_sha = str(plan_bank_sha).strip().lower()
        if len(plan_bank_sha) != 64 or any(c not in "0123456789abcdef" for c in plan_bank_sha):
            raise SystemExit(f"Invalid plan bank_sha256: {plan_bank_sha!r}")

    idx_s = raw.get("index_path")
    if idx_s:
        idx_p: pathlib.Path | None = pathlib.Path(os.path.expandvars(os.path.expanduser(str(idx_s))))
        if not idx_p.is_absolute():
            idx_p = (REPO_ROOT / idx_p).resolve()
    elif plan_bank_sha is not None or bank_type == "evalplus":
        idx_p = None
    else:
        idx_p = DEFAULT_INDEX_PATH

    raw["_model"] = model_cfg
    raw["_exam"] = exam_cfg
    raw["_task_format"] = task_format
    raw["_bank_type"] = bank_type
    raw["_gt_source"] = gt_source
    raw["_bank_path"] = str(bank_p)
    raw["_bank_sha256"] = plan_bank_sha
    raw["_index_path"] = str(idx_p) if idx_p is not None else None
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
        self.task_format: str = str(self.plan["_task_format"])
        self.bank_type: str = str(self.plan["_bank_type"])
        self.gt_source: str = str(self.plan["_gt_source"])
        self.bank_path = pathlib.Path(self.plan["_bank_path"])
        self.plan_bank_sha256: str | None = self.plan.get("_bank_sha256")
        self.index_path: pathlib.Path | None = (
            pathlib.Path(self.plan["_index_path"]) if self.plan.get("_index_path") else None
        )

        if self.calibrate_n is not None:
            if self.calibrate_n <= 0:
                raise SystemExit(f"--calibrate N must be > 0, got {self.calibrate_n}")
            if self.plan.get("difficulties"):
                cal_diffs = self.plan["difficulties"]
            elif self.bank_type == "evalplus":
                cal_diffs = ["humanevalplus", "mbppplus"]
            elif self.task_format == "stdio":
                cal_diffs = ["interview", "competition"]
            else:
                cal_diffs = ["medium", "hard"]
            loaded = load_bank_tasks(
                self.bank_path,
                index_path=self.index_path,
                expected_sha256=self.plan_bank_sha256,
                task_format=self.task_format,
                bank_type=self.bank_type,
                gt_source=self.gt_source,
                seed=self.seed,
                difficulties=cal_diffs,
                n_tasks=self.calibrate_n,
                verify_sha256=verify_bank_sha,
            )
            self.arms = ["B0"]
        else:
            loaded = load_bank_tasks(
                self.bank_path,
                index_path=self.index_path,
                expected_sha256=self.plan_bank_sha256,
                task_format=self.task_format,
                bank_type=self.bank_type,
                gt_source=self.gt_source,
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
        self.exam_cfg = self.plan["_exam"]
        self.worker_agent: str = str(self.model_cfg["agent"])
        self.exam_agent: str = str(self.exam_cfg["agent"])
        self.worker_model: str = str(self.model_cfg["model"])
        self.exam_model: str = str(self.exam_cfg["model"])
        self.uses_exam_arms: bool = any(a in _EXAM_USING_ARMS for a in self.arms)
        self.needs_pi: bool = (self.worker_agent == "pi") or (self.uses_exam_arms and self.exam_agent == "pi")
        self.needs_claude: bool = (self.worker_agent == "claude") or (self.uses_exam_arms and self.exam_agent == "claude")

        self.attempt_timeout_s = float(self.plan.get("attempt_timeout_s", 300))
        self.eval_timeout_s = float(self.plan.get("eval_timeout_s", 45))
        self.per_fn_timeout_s = float(self.plan.get("per_fn_timeout_s", 20))
        self.per_call_timeout_s = float(self.plan.get("per_call_timeout_s", 2.0))
        self.per_case_timeout_s = float(self.plan.get("per_case_timeout_s", self.per_call_timeout_s))
        self.eval_mem_mb = int(self.plan.get("eval_mem_mb", 1024))
        self.max_attempts = int(self.plan.get("max_attempts", 3))
        self.mv_num_inputs = int(self.plan.get("mv_num_inputs", 20))
        self.auth_retry_wait_s = float(self.plan.get("auth_retry_wait_s", 60.0))
        self.auth_max_retries = int(self.plan.get("auth_max_retries", 2))
        self.jobs = max(1, int(self.plan.get("jobs", 1)))

        self.pi_cfg_dst = self.root / "private_cfg"
        self.no_proxy_hosts: list[str] = []
        self.net_proxy: AllowlistUnixProxy | None = None
        self.results_path = self.root / "results.jsonl"

    def _active_claude_cfg(self) -> dict[str, Any]:
        if self.worker_agent == "claude":
            return self.model_cfg
        return self.exam_cfg

    def _active_pi_cfg(self) -> dict[str, Any]:
        if self.worker_agent == "pi":
            return self.model_cfg
        return self.exam_cfg

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
                    "bank_type": self.bank_type,
                    "bank_sha256": self.bank_sha256,
                    "task_format": self.task_format,
                    "gt_source": self.gt_source,
                    "per_case_timeout_s": self.per_case_timeout_s,
                    "seed": self.seed,
                    "git_head": self.git_head,
                    "agent": self.worker_agent,
                    "model": self.worker_model,
                    "providers": self.model_cfg.get("providers"),
                    "ctx": self.model_cfg.get("ctx"),
                    "exam_agent": self.exam_agent,
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

        if self.needs_pi:
            pi_cfg = self._active_pi_cfg()
            src_cfg_s = pi_cfg.get("pi_cfg_dir")
            src_cfg = (
                pathlib.Path(os.path.expandvars(os.path.expanduser(str(src_cfg_s))))
                if src_cfg_s
                else DEFAULT_PI_CFG_DIR
            )
            providers = pi_cfg.get("providers") or None
            if src_cfg.is_dir():
                self.no_proxy_hosts = prepare_sanitized_pi_cfg(src_cfg, self.pi_cfg_dst, allowed_providers=providers)
            else:
                self.pi_cfg_dst.mkdir(parents=True, exist_ok=True)

    def _run_preflight_negative_controls(self) -> None:
        other_arm_canary = self.root / "_nc_other_arm_prev"
        other_arm_canary.mkdir(parents=True, exist_ok=True)
        (other_arm_canary / "canary.txt").write_text("other-arm-secret\n", encoding="utf-8")

        combined_rep: dict[str, Any] = {"passed": True}

        if self.needs_pi:
            pi_cfg = self._active_pi_cfg()
            src_cfg_s = pi_cfg.get("pi_cfg_dir")
            src_cfg = (
                pathlib.Path(os.path.expandvars(os.path.expanduser(str(src_cfg_s))))
                if src_cfg_s
                else DEFAULT_PI_CFG_DIR
            )
            rep_pi = run_negative_controls(
                hidden_tests_path=self.bank_path,
                eval_dir=self.root,
                other_arm_ws=other_arm_canary,
                pi_cfg_dir=src_cfg,
            )
            combined_rep["pi"] = rep_pi
            if not rep_pi.get("passed"):
                combined_rep["passed"] = False
                atomic_write_json(self.root / "negative_controls.json", combined_rep)
                raise SystemExit(
                    f"Refusing to start: pi negative controls failed (see {self.root / 'negative_controls.json'}): "
                    f"leaks={rep_pi.get('leaks')} sanity={rep_pi.get('sanity')} "
                    f"eval_net={rep_pi.get('eval_net_isolated')}"
                )
            self._log("preflight negative_controls (pi) PASS")

        if self.needs_claude:
            c_cfg = self._active_claude_cfg()
            creds_src_s = c_cfg.get("credentials_path")
            creds_src = (
                pathlib.Path(os.path.expandvars(os.path.expanduser(str(creds_src_s))))
                if creds_src_s
                else None
            )
            claude_bin_s = c_cfg.get("claude_bin")
            rep_c = run_claude_negative_controls(
                hidden_tests_path=self.bank_path,
                eval_dir=self.root,
                other_arm_ws=other_arm_canary,
                credentials_src=creds_src,
                claude_bin_override=claude_bin_s,
            )
            combined_rep["claude"] = rep_c
            if not rep_c.get("passed"):
                combined_rep["passed"] = False
                atomic_write_json(self.root / "negative_controls.json", combined_rep)
                raise SystemExit(
                    f"Refusing to start: Claude negative controls failed (see {self.root / 'negative_controls.json'}): "
                    f"leaks={rep_c.get('leaks')} sanity={rep_c.get('sanity')} "
                    f"net={rep_c.get('net')} eval_net={rep_c.get('eval_net_isolated')}"
                )
            self._log("preflight negative_controls (claude) PASS")

        atomic_write_json(self.root / "negative_controls.json", combined_rep)

    def _prepare_ro_mountpoints(
        self,
        ws_dir: pathlib.Path,
        work_ro_binds: list[tuple[pathlib.Path, str]] | None,
    ) -> None:
        if not work_ro_binds:
            return
        for _, guest_p in work_ro_binds:
            if guest_p.startswith("/work/"):
                rel = guest_p[len("/work/"):]
                mp = ws_dir / rel
                mp.parent.mkdir(parents=True, exist_ok=True)
                if not mp.exists():
                    mp.write_text("", encoding="utf-8")

    def _run_claude_session(
        self,
        *,
        ws_dir: pathlib.Path,
        prompt: str,
        model_id: str,
        log_path: pathlib.Path,
        claude_cfg: dict[str, Any] | None = None,
        work_ro_binds: list[tuple[pathlib.Path, str]] | None = None,
        extra_env: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Run one Claude Code session inside E1's `--unshare-net` allowlist-proxy bwrap sandbox.

        Copies host `~/.claude/.credentials.json` fresh into a per-session credential dir right before
        each attempt. On auth errors ("OAuth token revoked", "Failed to authenticate", 401), waits
        `auth_retry_wait_s` (default 60s), re-copies host credentials, and retries up to `auth_max_retries`
        (default 2) times; if still failing, marks `infra_error=True`.
        """
        assert self.net_proxy is not None, "allowlist proxy must be running"
        cfg = claude_cfg if claude_cfg is not None else self._active_claude_cfg()
        creds_src_s = cfg.get("credentials_path")
        creds_src = (
            pathlib.Path(os.path.expandvars(os.path.expanduser(str(creds_src_s))))
            if creds_src_s
            else None
        )
        claude_bin_s = cfg.get("claude_bin")

        cmd = build_claude_cli_argv(model_id, prompt)
        env_map: dict[str, str] = {}
        if cfg.get("fake_mode"):
            env_map["FL_FAKE_MODE"] = str(cfg["fake_mode"])
        if extra_env:
            env_map.update(extra_env)

        self._prepare_ro_mountpoints(ws_dir, work_ro_binds)

        total_wall_s = 0.0
        res: dict[str, Any] = {"rc": None, "wall_s": 0.0, "timed_out": False}
        usage: dict[str, Any] | None = None
        auth_err = False
        auth_retries = 0

        with tempfile.TemporaryDirectory(prefix="fl_claude_creds_") as creds_tmp:
            creds_dir = pathlib.Path(creds_tmp)
            for attempt_idx in range(self.auth_max_retries + 1):
                creds_file = prepare_claude_credentials(creds_dir, src_creds_path=creds_src)
                argv = build_claude_worker_bwrap_argv(
                    cmd,
                    workspace_dir=ws_dir,
                    proxy_sock_path=self.net_proxy.sock_path,
                    credentials_file=creds_file,
                    claude_bin_override=claude_bin_s,
                    extra_env=env_map or None,
                )
                if work_ro_binds:
                    argv = insert_work_ro_binds(argv, work_ro_binds)

                res = run_sandboxed(argv, timeout_s=self.attempt_timeout_s, log_path=log_path)
                total_wall_s += float(res.get("wall_s") or 0.0)
                usage = usage_from_claude_log(log_path)
                auth_err = _is_claude_auth_error(usage, log_path, res.get("rc"))

                if auth_err and attempt_idx < self.auth_max_retries:
                    auth_retries += 1
                    backup_log = log_path.with_name(f"{log_path.stem}.auth_try{attempt_idx + 1}{log_path.suffix}")
                    try:
                        shutil.copy2(log_path, backup_log)
                    except OSError:
                        pass
                    self._log(
                        f"claude_auth_error retry={auth_retries}/{self.auth_max_retries} "
                        f"wait={self.auth_retry_wait_s}s model={model_id}"
                    )
                    if self.auth_retry_wait_s > 0:
                        time.sleep(self.auth_retry_wait_s)
                    continue
                break

        is_infra = bool(auth_err)
        if not is_infra:
            if usage is None:
                is_infra = True
            elif usage["calls"] == 0 and (
                usage["errors"] > 0
                or res["rc"] != 0
                or (usage.get("final_error") and _INFRA_ERR_RE.search(usage["final_error"]))
            ):
                is_infra = True

        return {
            "agent": "claude",
            "model": model_id,
            "rc": res["rc"],
            "wall_s": round(total_wall_s, 3),
            "timed_out": res["timed_out"],
            "usage": usage,
            "cost_usd": usage.get("cost_usd") if isinstance(usage, dict) else None,
            "auth_retries": auth_retries,
            "auth_error": auth_err,
            "infra_error": is_infra,
        }

    def _run_pi_session(
        self,
        *,
        ws_dir: pathlib.Path,
        prompt: str,
        model_id: str,
        provider: str,
        log_path: pathlib.Path,
        pi_cfg: dict[str, Any] | None = None,
        work_ro_binds: list[tuple[pathlib.Path, str]] | None = None,
        extra_env: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Run one `pi` session inside E1's bwrap sandbox with identical CLI and usage parsing."""
        cfg = pi_cfg if pi_cfg is not None else self._active_pi_cfg()
        fake_agent = cfg.get("fake_agent")
        extra_ro: list[tuple[pathlib.Path, str]] = []
        env_map: dict[str, str] = {}
        if cfg.get("fake_mode"):
            env_map["FL_FAKE_MODE"] = str(cfg["fake_mode"])
        if extra_env:
            env_map.update(extra_env)

        if fake_agent:
            fa_path = pathlib.Path(os.path.expandvars(os.path.expanduser(str(fake_agent))))
            if not fa_path.is_absolute():
                fa_path = (REPO_ROOT / fa_path).resolve()
            extra_ro.append((fa_path, "/opt/bin/fake_agent.py"))
            cmd = ["python3", "/opt/bin/fake_agent.py", "--prompt", prompt]
            mount_pi = False
        else:
            cmd = [
                "pi",
                "-p",
                "--mode", "json",
                "--no-session",
                "--no-extensions",
                "--offline",
                "--provider", provider,
                "--model", model_id,
                prompt,
            ]
            mount_pi = True

        self._prepare_ro_mountpoints(ws_dir, work_ro_binds)
        argv = build_worker_bwrap_argv(
            cmd,
            workspace_dir=ws_dir,
            pi_cfg_dir=self.pi_cfg_dst,
            extra_ro_binds=extra_ro,
            no_proxy_hosts=self.no_proxy_hosts,
            extra_env=env_map or None,
            mount_pi=mount_pi,
        )
        if work_ro_binds:
            argv = insert_work_ro_binds(argv, work_ro_binds)

        res = run_sandboxed(argv, timeout_s=self.attempt_timeout_s, log_path=log_path)
        usage = usage_from_pi_log(log_path)
        is_infra = False
        if not fake_agent:
            if usage is None:
                is_infra = True
            elif usage["calls"] == 0 and (
                usage["errors"] > 0
                or res["rc"] != 0
                or (usage.get("final_error") and _INFRA_ERR_RE.search(usage["final_error"]))
            ):
                is_infra = True

        return {
            "agent": "pi",
            "provider": provider,
            "model": model_id,
            "rc": res["rc"],
            "wall_s": res["wall_s"],
            "timed_out": res["timed_out"],
            "usage": usage,
            "cost_usd": None,
            "infra_error": is_infra,
        }

    def _run_agent_session(
        self,
        *,
        cfg: dict[str, Any],
        ws_dir: pathlib.Path,
        prompt: str,
        log_path: pathlib.Path,
        provider: str = "fake",
        work_ro_binds: list[tuple[pathlib.Path, str]] | None = None,
        extra_env: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        agent = str(cfg["agent"])
        model_id = str(cfg["model"])
        if agent == "pi":
            return self._run_pi_session(
                ws_dir=ws_dir,
                prompt=prompt,
                model_id=model_id,
                provider=provider,
                log_path=log_path,
                pi_cfg=cfg,
                work_ro_binds=work_ro_binds,
                extra_env=extra_env,
            )
        return self._run_claude_session(
            ws_dir=ws_dir,
            prompt=prompt,
            model_id=model_id,
            log_path=log_path,
            claude_cfg=cfg,
            work_ro_binds=work_ro_binds,
            extra_env=extra_env,
        )

    def _eval_on_cases(
        self,
        sol_src: str,
        task: dict[str, Any],
        cases: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if self.task_format == "stdio":
            return evaluate_stdio_on_cases(
                sol_src,
                cases,
                per_case_timeout_s=self.per_case_timeout_s,
                total_timeout_s=self.eval_timeout_s,
                mem_limit_mb=self.eval_mem_mb,
            )
        ep = task["entry_point"]
        assert ep is not None
        return evaluate_solution_on_cases(
            sol_src,
            ep,
            cases,
            per_fn_timeout_s=self.per_fn_timeout_s,
            total_timeout_s=self.eval_timeout_s,
            mem_limit_mb=self.eval_mem_mb,
            atol=float(task.get("atol") or 0.0),
            cmp_mode=str(task.get("cmp_mode") or "exact"),
        )

    def _collect_outputs(self, sol_src: str, entry_point: str | None, mv_inputs: list[Any]) -> dict[str, Any]:
        if self.task_format == "stdio":
            return collect_stdio_outputs_in_sandbox(
                sol_src,
                mv_inputs,
                per_case_timeout_s=self.per_case_timeout_s,
                total_timeout_s=self.eval_timeout_s,
                mem_limit_mb=self.eval_mem_mb,
            )
        assert entry_point is not None
        return collect_outputs_in_sandbox(
            sol_src,
            entry_point,
            mv_inputs,
            per_call_timeout_s=self.per_call_timeout_s,
            total_timeout_s=self.eval_timeout_s,
            mem_limit_mb=self.eval_mem_mb,
        )

    def _run_test_writer_session(
        self,
        *,
        task: dict[str, Any],
        cell_dir: pathlib.Path,
        cfg: dict[str, Any],
        provider: str,
        role: str,
        use_exam_prompt: bool = False,
    ) -> dict[str, Any]:
        """Run a separate session that writes `/work/tests_spec.py`, then freeze & parse it."""
        tw_dir = cell_dir / "test_writer"
        tw_dir.mkdir(parents=True, exist_ok=True)
        prompt = build_exam_writer_prompt(task) if use_exam_prompt else build_test_writer_prompt(task)
        with tempfile.TemporaryDirectory(prefix=f"fl_tw_{task['task_id']}_{role}_") as ws_tmp:
            ws_p = pathlib.Path(ws_tmp)
            wres = self._run_agent_session(
                cfg=cfg,
                ws_dir=ws_p,
                prompt=prompt,
                log_path=tw_dir / "agent.log",
                provider=provider,
                extra_env={"FL_ROLE": role, "FL_TASK_ID": task["task_id"]},
            )
            spec_p = ws_p / "tests_spec.py"
            spec_text = spec_p.read_text(encoding="utf-8", errors="replace") if spec_p.is_file() else ""

        frozen_path = cell_dir / "frozen_tests_spec.py"
        frozen_sha = atomic_write_text(frozen_path, spec_text)
        cases, parse_err = parse_tests_spec_text(spec_text, task_format=self.task_format)
        session_entry = {
            "role": role,
            **wres,
            "frozen_sha256": frozen_sha,
            "n_cases": len(cases),
            "parse_error": parse_err,
        }
        atomic_write_json(
            cell_dir / "frozen_tests_meta.json",
            {
                "role": role,
                "agent": cfg["agent"],
                "model": cfg["model"],
                "sha256": frozen_sha,
                "n_cases": len(cases),
                "parse_error": parse_err,
                "session": session_entry,
            },
        )
        return {
            "role": role,
            "frozen_path": frozen_path,
            "frozen_sha256": frozen_sha,
            "cases": cases,
            "parse_error": parse_err,
            "session": session_entry,
        }

    def _get_or_create_cached_exam(
        self,
        *,
        task: dict[str, Any],
        provider: str,
    ) -> dict[str, Any]:
        """Generate (once per task) or load the cached Haiku exam under `ROOT/exam_cache/<tid>/`."""
        tid = task["task_id"]
        cache_dir = self.root / "exam_cache" / tid
        meta_p = cache_dir / "exam_meta.json"
        spec_p = cache_dir / "frozen_tests_spec.py"

        with _EXAM_CACHE_LOCK:
            if meta_p.is_file() and spec_p.is_file():
                meta = json.loads(meta_p.read_text(encoding="utf-8"))
                spec_text = spec_p.read_text(encoding="utf-8", errors="replace")
                cases, parse_err = parse_tests_spec_text(spec_text, task_format=self.task_format)
                return {
                    "reused": True,
                    "frozen_path": spec_p,
                    "frozen_sha256": meta["sha256"],
                    "cases": cases,
                    "parse_error": parse_err,
                    "session": meta["session"],
                }

        # Run outside lock so multiple tasks can call Haiku concurrently when jobs > 1
        cache_dir.mkdir(parents=True, exist_ok=True)
        tw = self._run_test_writer_session(
            task=task,
            cell_dir=cache_dir,
            cfg=self.exam_cfg,
            provider=provider,
            role="xmh_exam_writer",
            use_exam_prompt=True,
        )
        with _EXAM_CACHE_LOCK:
            if not tw["session"].get("infra_error") and not meta_p.is_file():
                atomic_write_json(
                    meta_p,
                    {
                        "task_id": tid,
                        "agent": self.exam_agent,
                        "model": self.exam_model,
                        "sha256": tw["frozen_sha256"],
                        "n_cases": len(tw["cases"]),
                        "parse_error": tw["parse_error"],
                        "cost_usd": tw["session"].get("cost_usd"),
                        "session": tw["session"],
                    },
                )
        return {
            "reused": False,
            "frozen_path": tw["frozen_path"],
            "frozen_sha256": tw["frozen_sha256"],
            "cases": tw["cases"],
            "parse_error": tw["parse_error"],
            "session": tw["session"],
        }

    def _run_input_gen_session(
        self,
        *,
        task: dict[str, Any],
        cell_dir: pathlib.Path,
        cfg: dict[str, Any],
        provider: str,
    ) -> dict[str, Any]:
        """Run a separate exam-model session that writes `/work/gen_inputs.py`, then run it in eval sandbox."""
        ig_dir = cell_dir / "input_gen"
        ig_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=f"fl_ig_{task['task_id']}_") as ws_tmp:
            ws_p = pathlib.Path(ws_tmp)
            wres = self._run_agent_session(
                cfg=cfg,
                ws_dir=ws_p,
                prompt=build_input_gen_prompt(task, n_inputs=self.mv_num_inputs),
                log_path=ig_dir / "agent.log",
                provider=provider,
                extra_env={"FL_ROLE": "mv_input_gen", "FL_TASK_ID": task["task_id"]},
            )
            gen_p = ws_p / "gen_inputs.py"
            gen_text = gen_p.read_text(encoding="utf-8", errors="replace") if gen_p.is_file() else ""

        gen_copy = cell_dir / "gen_inputs.py"
        gen_sha = atomic_write_text(gen_copy, gen_text)
        if self.task_format == "stdio":
            if gen_text.strip():
                gen_run = run_stdio_input_generator_in_sandbox(
                    gen_text,
                    max_inputs=self.mv_num_inputs,
                    timeout_s=min(15.0, self.eval_timeout_s),
                    mem_limit_mb=self.eval_mem_mb,
                )
            else:
                gen_run = {"ok": False, "inputs": [], "error": "missing_gen_inputs_py", "wall_s": 0.0}
            # Combine generated stdin strings + statement examples' inputs ONLY (no expected outputs)
            vis_inputs = [str(c["input"]) for c in task["visible_tests"]]
            combined_inputs: list[Any] = deduplicate_stdio_inputs(list(gen_run.get("inputs") or []) + vis_inputs)
            n_vis_inputs = len(vis_inputs)
        else:
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
            n_vis_inputs = len(vis_encoded)

        meta = {
            "role": "mv_input_gen",
            "agent": cfg["agent"],
            "model": cfg["model"],
            "gen_sha256": gen_sha,
            "n_generated_inputs": len(gen_run.get("inputs") or []),
            "n_visible_arg_inputs": n_vis_inputs,
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
        provider: str,
        prev_ws_dir: pathlib.Path | None = None,
        work_ro_binds: list[tuple[pathlib.Path, str]] | None = None,
        feedback_sent: str | None = None,
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

            wres = self._run_agent_session(
                cfg=self.model_cfg,
                ws_dir=ws_p,
                prompt=prompt,
                log_path=att_dir / "agent.log",
                provider=provider,
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

        eval_res = self._eval_on_cases(cand_src, task, task["eval_hidden"])
        fb_bytes = len(feedback_sent.encode("utf-8")) if feedback_sent else 0
        att_entry = {
            "attempt": att,
            **wres,
            "candidate_sha256": cand_sha,
            "feedback_sent": feedback_sent,
            "feedback_bytes": fb_bytes,
            "gate_verdict": None,
            "gate_detail": None,
            "eval_verdict": bool(eval_res["passed"]),
            "eval_detail": eval_res,
        }
        return att_entry, cand_src, next_ws_copy

    def _run_gated_retry_loop(
        self,
        *,
        task: dict[str, Any],
        arm: str,
        cell_dir: pathlib.Path,
        coder_prompt: str,
        gate_cases: list[dict[str, Any]],
        provider: str,
        work_ro_binds: list[tuple[pathlib.Path, str]] | None = None,
    ) -> tuple[list[dict[str, Any]], list[str], int, bool]:
        """Run up to `max_attempts` fresh-workspace attempts gated on `gate_cases` with retry feedback."""
        attempts_meta: list[dict[str, Any]] = []
        cand_sources: list[str] = []
        delivered_idx = 0
        gate_passed = False
        feedback_text: str | None = None

        for att in range(1, self.max_attempts + 1):
            prompt = f"{coder_prompt}\n\n{feedback_text}" if feedback_text else coder_prompt
            att_e, cand_src, _ = self._run_single_coding_attempt(
                task=task,
                arm=arm,
                att=att,
                att_dir=cell_dir / f"attempt_{att}",
                prompt=prompt,
                provider=provider,
                work_ro_binds=work_ro_binds,
                feedback_sent=feedback_text,
            )
            g_res = self._eval_on_cases(cand_src, task, gate_cases)
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
            if att < self.max_attempts:
                feedback_text = build_retry_feedback(task, gate_cases, g_res)

        return attempts_meta, cand_sources, delivered_idx, gate_passed

    def _run_task_arm(self, task: dict[str, Any], arm: str, *, provider: str) -> dict[str, Any]:
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
        exam_cost_usd: float | None = None

        # ── B0: 1 attempt, deliver it ────────────────────────────────────────
        if arm == "B0":
            att_e, cand_src, _ = self._run_single_coding_attempt(
                task=task,
                arm=arm,
                att=1,
                att_dir=cell_dir / "attempt_1",
                prompt=base_prompt,
                provider=provider,
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
                    provider=provider,
                    prev_ws_dir=prev_ws,
                )
                attempts_meta.append(att_e)
                cand_sources.append(cand_src)
            delivered_idx = len(attempts_meta) - 1

        # ── GT / EX: fresh attempts gated on GT source or visible_tests ──────
        elif arm in ("GT", "EX"):
            if arm == "GT":
                gate_cases = task["visible_tests"] if self.gt_source == "visible" else task["gate_hidden"]
                judge_meta = {"gt_source": self.gt_source, "n_gate_cases": len(gate_cases)}
            else:
                gate_cases = task["visible_tests"]
                judge_meta = {"n_gate_cases": len(gate_cases)}
            attempts_meta, cand_sources, delivered_idx, gate_passed = self._run_gated_retry_loop(
                task=task,
                arm=arm,
                cell_dir=cell_dir,
                coder_prompt=base_prompt,
                gate_cases=gate_cases,
                provider=provider,
            )

        # ── TF / XM: test-writer session + frozen tests gate ─────────────────
        elif arm in ("TF", "XM"):
            tw_cfg = self.model_cfg if arm == "TF" else self.exam_cfg
            tw = self._run_test_writer_session(
                task=task,
                cell_dir=cell_dir,
                cfg=tw_cfg,
                provider=provider,
                role="tf_test_writer" if arm == "TF" else "xm_exam_writer",
            )
            extra_sessions.append(tw["session"])
            if arm == "XM":
                exam_cost_usd = tw["session"].get("cost_usd")
            judge_meta = {
                "frozen_tests_sha256": tw["frozen_sha256"],
                "n_generated_tests": len(tw["cases"]),
                "parse_error": tw["parse_error"],
                "test_writer_agent": tw_cfg["agent"],
                "test_writer_model": tw_cfg["model"],
            }
            if not tw["cases"]:
                undetermined = True
                undetermined_reason = tw["parse_error"] or "zero_cases"
                gate_passed = None
                att_e, cand_src, _ = self._run_single_coding_attempt(
                    task=task,
                    arm=arm,
                    att=1,
                    att_dir=cell_dir / "attempt_1",
                    prompt=base_prompt,
                    provider=provider,
                )
                attempts_meta.append(att_e)
                cand_sources.append(cand_src)
                delivered_idx = 0
            else:
                work_ro = [(tw["frozen_path"], "/work/tests_spec.py")] if arm == "TF" else None
                coder_prompt = build_tf_coder_prompt(task) if arm == "TF" else base_prompt
                attempts_meta, cand_sources, delivered_idx, gate_passed = self._run_gated_retry_loop(
                    task=task,
                    arm=arm,
                    cell_dir=cell_dir,
                    coder_prompt=coder_prompt,
                    gate_cases=tw["cases"],
                    provider=provider,
                    work_ro_binds=work_ro,
                )

        # ── XMH / XMVH: cached Haiku exam (worker never sees exam) ───────────
        elif arm in ("XMH", "XMVH"):
            exam = self._get_or_create_cached_exam(task=task, provider=provider)
            if exam["reused"]:
                reused_from["exam_cache"] = True
                reused_cost_entries.append(exam["session"])
            else:
                reused_from["exam_cache"] = False
                extra_sessions.append(exam["session"])
            exam_cost_usd = exam["session"].get("cost_usd")

            exam_cases = exam["cases"]
            judge_meta = {
                "exam_sha256": exam["frozen_sha256"],
                "exam_agent": self.exam_agent,
                "exam_model": self.exam_model,
                "exam_cached_reused": bool(exam["reused"]),
                "exam_cost_usd": exam_cost_usd,
                "n_exam_cases_raw": len(exam_cases),
                "parse_error": exam["parse_error"],
            }

            if arm == "XMH":
                if not exam_cases:
                    undetermined = True
                    undetermined_reason = exam["parse_error"] or "zero_cases"
                    gate_passed = None
                    att_e, cand_src, _ = self._run_single_coding_attempt(
                        task=task,
                        arm=arm,
                        att=1,
                        att_dir=cell_dir / "attempt_1",
                        prompt=base_prompt,
                        provider=provider,
                    )
                    attempts_meta.append(att_e)
                    cand_sources.append(cand_src)
                    delivered_idx = 0
                else:
                    judge_meta["n_gate_cases"] = len(exam_cases)
                    attempts_meta, cand_sources, delivered_idx, gate_passed = self._run_gated_retry_loop(
                        task=task,
                        arm=arm,
                        cell_dir=cell_dir,
                        coder_prompt=base_prompt,
                        gate_cases=exam_cases,
                        provider=provider,
                        work_ro_binds=None,
                    )
            else:
                # XMVH: self-check Haiku exam against statement examples
                if not exam_cases:
                    undetermined = True
                    undetermined_reason = exam["parse_error"] or "zero_cases"
                    gate_passed = None
                    judge_meta["self_check"] = {
                        "self_check_failed": False,
                        "n_exam_raw": 0,
                        "n_gate_cases": 0,
                    }
                    att_e, cand_src, _ = self._run_single_coding_attempt(
                        task=task,
                        arm=arm,
                        att=1,
                        att_dir=cell_dir / "attempt_1",
                        prompt=base_prompt,
                        provider=provider,
                    )
                    attempts_meta.append(att_e)
                    cand_sources.append(cand_src)
                    delivered_idx = 0
                else:
                    sc = self_check_xmvh_exam(
                        exam_cases,
                        task["visible_tests"],
                        task_format=self.task_format,
                        atol=float(task.get("atol") or 0.0),
                        cmp_mode=str(task.get("cmp_mode") or "exact"),
                    )
                    judge_meta["self_check"] = {k: v for k, v in sc.items() if k != "gate_cases"}
                    gate_cases_xmvh = sc["gate_cases"]
                    judge_meta["n_gate_cases"] = len(gate_cases_xmvh)
                    if sc["self_check_failed"] or not gate_cases_xmvh:
                        undetermined = True
                        undetermined_reason = (
                            "exam_self_check_failed" if sc["self_check_failed"] else "zero_gate_cases"
                        )
                        gate_passed = None
                        att_e, cand_src, _ = self._run_single_coding_attempt(
                            task=task,
                            arm=arm,
                            att=1,
                            att_dir=cell_dir / "attempt_1",
                            prompt=base_prompt,
                            provider=provider,
                        )
                        attempts_meta.append(att_e)
                        cand_sources.append(cand_src)
                        delivered_idx = 0
                    else:
                        attempts_meta, cand_sources, delivered_idx, gate_passed = self._run_gated_retry_loop(
                            task=task,
                            arm=arm,
                            cell_dir=cell_dir,
                            coder_prompt=base_prompt,
                            gate_cases=gate_cases_xmvh,
                            provider=provider,
                            work_ro_binds=None,
                        )

        # ── MV: 3 fresh attempts + exam-model gen_inputs.py + output clustering ─
        elif arm == "MV":
            ig_meta = self._run_input_gen_session(
                task=task, cell_dir=cell_dir, cfg=self.exam_cfg, provider=provider
            )
            extra_sessions.append(ig_meta["session"])
            mv_inputs = ig_meta["inputs"]

            output_tags: list[list[str]] = []
            output_details: list[dict[str, Any]] = []
            for att in range(1, self.max_attempts + 1):
                att_e, cand_src, _ = self._run_single_coding_attempt(
                    task=task,
                    arm=arm,
                    att=att,
                    att_dir=cell_dir / f"attempt_{att}",
                    prompt=base_prompt,
                    provider=provider,
                )
                out_res = self._collect_outputs(cand_src, ep, mv_inputs)
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

        # ── CT: reuse MV's 3 solutions + inputs and XM/cached exam tests ─────
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
                        "feedback_sent": prev_a.get("feedback_sent"),
                        "feedback_bytes": int(prev_a.get("feedback_bytes") or 0),
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
                ig_meta = self._run_input_gen_session(
                    task=task, cell_dir=cell_dir, cfg=self.exam_cfg, provider=provider
                )
                extra_sessions.append(ig_meta["session"])
                mv_inputs = ig_meta["inputs"]
                output_tags = []
                for att in range(1, self.max_attempts + 1):
                    att_e, cand_src, _ = self._run_single_coding_attempt(
                        task=task,
                        arm=arm,
                        att=att,
                        att_dir=cell_dir / f"attempt_{att}",
                        prompt=base_prompt,
                        provider=provider,
                    )
                    out_res = self._collect_outputs(cand_src, ep, mv_inputs)
                    output_tags.append(out_res["tags"])
                    attempts_meta.append(att_e)
                    cand_sources.append(cand_src)

            # 2) Reuse XM's generated tests if XM already completed for this task
            if (xm_dir / "done.json").is_file() and (xm_dir / "frozen_tests_spec.py").is_file() and (xm_dir / "record.json").is_file():
                reused_from["xm"] = True
                xm_rec = json.loads((xm_dir / "record.json").read_text(encoding="utf-8"))
                xm_spec_text = (xm_dir / "frozen_tests_spec.py").read_text(encoding="utf-8", errors="replace")
                xm_cases, xm_parse_err = parse_tests_spec_text(xm_spec_text, task_format=self.task_format)
                for ex_s in xm_rec.get("extra_sessions") or []:
                    reused_cost_entries.append(ex_s)
                    if exam_cost_usd is None:
                        exam_cost_usd = ex_s.get("cost_usd")
            else:
                reused_from["xm"] = False
                tw = self._run_test_writer_session(
                    task=task, cell_dir=cell_dir, cfg=self.exam_cfg, provider=provider, role="ct_exam_writer"
                )
                extra_sessions.append(tw["session"])
                exam_cost_usd = tw["session"].get("cost_usd")
                xm_cases = tw["cases"]
                xm_parse_err = tw["parse_error"]

            # 3) Score each solution on XM tests + MV agreement
            tests_passed_list: list[int] = []
            for cand_src in cand_sources:
                if xm_cases:
                    t_ev = self._eval_on_cases(cand_src, task, xm_cases)
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
        if arm in GATED_RETRY_ARMS:
            false_reject = any(
                (a.get("gate_verdict") is False) and bool(a.get("eval_verdict"))
                for a in attempts_meta
            )
        elif arm in ("MV", "CT"):
            false_reject = bool((not delivered_correct) and any(bool(a.get("eval_verdict")) for a in attempts_meta))
        else:
            false_reject = False

        att_conf = _compute_attempt_confusion(attempts_meta)
        feedback_bytes_total = sum(int(a.get("feedback_bytes") or 0) for a in attempts_meta)
        feedback_sent_count = sum(1 for a in attempts_meta if a.get("feedback_sent"))

        # Standalone cost (full cost of running this arm) vs incremental API cost actually spent by this cell
        if reused_cost_entries:
            own_entries: list[dict[str, Any]] = []
            if not reused_from.get("mv"):
                own_entries.extend(attempts_meta)
            own_entries.extend(extra_sessions)
            inc_totals = _sum_usage_entries(own_entries)
            full_totals = _sum_usage_entries(own_entries + reused_cost_entries)
            if inc_totals["cost_usd"] is None and full_totals["cost_usd"] is not None:
                inc_totals["cost_usd"] = 0.0
        else:
            full_totals = _sum_usage_entries(attempts_meta + extra_sessions)
            inc_totals = full_totals

        record: dict[str, Any] = {
            "schema": RESULT_SCHEMA,
            "ts_utc": utc_now_iso(),
            "plan_id": self.plan["id"],
            "task_id": tid,
            "task_format": self.task_format,
            "gt_source": self.gt_source,
            "difficulty": task["difficulty"],
            "entry_point": ep,
            "arm": arm,
            "agent": self.worker_agent,
            "provider": provider if self.worker_agent == "pi" else None,
            "model": self.worker_model,
            "exam_agent": self.exam_agent,
            "exam_model": self.exam_model,
            "exam_cost_usd": exam_cost_usd,
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
            "feedback_bytes_total": feedback_bytes_total,
            "feedback_sent_count": feedback_sent_count,
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
            f"att={len(attempts_meta)} deliv={delivered_idx + 1} fb={feedback_bytes_total}B "
            f"void={record['infra_void']} cost=${record['incremental_cost_usd']} wall={record['wall_s']}s"
        )
        return record

    def _run_one_task(self, task_idx: int, task: dict[str, Any]) -> list[dict[str, Any]]:
        providers = self.model_cfg.get("providers") or ["fake"]
        provider = providers[task_idx % len(providers)]
        # Ensure XMH runs before XMVH (exam cache reuse), and MV/XM run before CT
        def _arm_sort_key(item: tuple[int, str]) -> tuple[int, int]:
            idx, a = item
            if a == "CT":
                return (2, idx)
            if a == "XMVH":
                return (1, idx)
            return (0, idx)

        ordered_arms = [a for _, a in sorted(enumerate(self.arms), key=_arm_sort_key)]
        out: list[dict[str, Any]] = []
        for arm in ordered_arms:
            out.append(self._run_task_arm(task, arm, provider=provider))
        return out

    def run(self) -> dict[str, Any]:
        self._init_root_and_check_resume()
        records: list[dict[str, Any]] = []
        try:
            self._run_preflight_negative_controls()

            if self.needs_claude:
                c_cfg = self._active_claude_cfg()
                allowed_connect = _parse_allowed_connect_hosts(c_cfg.get("allowed_connect_hosts"))
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
                for i, t in enumerate(self.tasks):
                    records.extend(self._run_one_task(i, t))
            else:
                with concurrent.futures.ThreadPoolExecutor(max_workers=self.jobs) as ex:
                    futs = [ex.submit(self._run_one_task, i, t) for i, t in enumerate(self.tasks)]
                    for fut in concurrent.futures.as_completed(futs):
                        records.extend(fut.result())
        finally:
            if self.net_proxy is not None:
                self.net_proxy.stop()
                self.net_proxy = None
            kill_all_live()

        summary: dict[str, Any] = {
            "root": str(self.root),
            "results_jsonl": str(self.results_path),
            "bank_sha256": self.bank_sha256,
            "bank_type": self.bank_type,
            "gt_source": self.gt_source,
            "n_tasks": len(self.tasks),
            "n_skipped": len(self.skipped_tasks),
            "arms": self.arms,
        }
        if self.calibrate_n is not None:
            by_diff: dict[str, dict[str, Any]] = {}
            valid_recs = [r for r in records if not r.get("infra_void")]
            if self.bank_type == "evalplus":
                default_diffs: tuple[str, ...] = ("humanevalplus", "mbppplus")
            elif self.task_format == "stdio":
                default_diffs = ("introductory", "interview", "competition")
            else:
                default_diffs = ("medium", "hard")
            diff_order = list(dict.fromkeys([
                *(self.plan.get("difficulties") or default_diffs),
                *(str(r.get("difficulty") or "unknown") for r in valid_recs),
            ]))
            for diff in diff_order:
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
