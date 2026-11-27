#!/usr/bin/env python3
"""Experiment T runner ("send unsupported claims back for revision", cycle 0 only).

For each (set, rep):
  1. Run initial cycle-0 draft (`c0`) against revision-0 pages served by `source_server.py`
     through Vacant's per-worker egress proxy (`vacant trace egress`) and observe-mode hook.
     Snapshot `ws/` and `vh/`.
  2. For each arm in shuffled order (`A`, `G`, `T`, `T0`):
     - Restore `c0` snapshot to the same workspace path (preserving trace chain continuity).
     - A  : native c0 draft only (0 extra rounds).
     - G  : up to `max_rounds` (2) extra rounds with fixed generic review prompt
            (`GENERIC_REVIEW_PROMPT`), no record info.
     - T  : recompute per-line F1/F3 flags from RECORDS ONLY after each round; send back
            ONLY flagged lines + problem kind + agent's own egress URLs; stop when 0 flagged.
     - T0 : same stop rule as T, but count-only feedback (no line ids).
     - Append every feedback message (exact text) and triggering evidence (flag set,
       fetched-page list, round) as an Ed25519-signed event to `feedback_chain.ndjson`
       (`vacant_network.logbook`).

Usage:
  python3 ops/d2/run_expT.py run --plan ops/d2/plans/expT_qwen9b.json --root <dir>
  python3 ops/d2/run_expT.py run --plan <plan.json> --root <dir> --fake
"""
from __future__ import annotations

import argparse
import atexit
import datetime as dt
import fcntl
import hashlib
import hmac
import json
import os
import pathlib
import random
import re
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from typing import Any

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
if str(REPO / "ops" / "redo") not in sys.path:
    sys.path.insert(0, str(REPO / "ops" / "redo"))

from redo import usage_from_log  # noqa: E402
from run_d2 import (  # noqa: E402
    CLAUDE_ALLOWED_TOOLS,
    CLAUDE_DISALLOWED_TOOLS,
    CLAUDE_NO_PROXY,
    NO_PROXY,
    PROMPTS,
    InfraError,
    rmtree_retry,
    usage_from_claude_log,
)
import expT_feedback as FB  # noqa: E402
from vacant_network.identity import Identity  # noqa: E402
from vacant_network.logbook import Logbook  # noqa: E402
from vacant_network.trace import sources as S  # noqa: E402

LOCK = threading.Lock()


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha_file(p: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(p: pathlib.Path, obj: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(f".{p.name}.tmp.{os.getpid()}.{threading.get_ident()}")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, p)


def load_materials_specs(plan: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    """Load one or more material directories from `plan['materials']`.

    Returns:
      sets_meta: qualified_set_id -> {
          'set_id', 'orig_set', 'mat_dir', 'domain', 'pages', 'index', 'claims'
      }
      manifest_shas: label -> sha256
    Note: Does NOT expose ground-truth answers in `claims`; only template metadata.
    """
    raw = plan["materials"]
    entries = raw if isinstance(raw, list) else [raw]
    sets_meta: dict[str, dict[str, Any]] = {}
    manifest_shas: dict[str, str] = {}

    for idx, entry in enumerate(entries):
        prefix = str(entry.get("prefix") or "").strip()
        mat_dir = pathlib.Path(os.path.expandvars(os.path.expanduser(str(entry["dir"]))))
        man_path = mat_dir / "manifest.json"
        if not man_path.is_file():
            raise SystemExit(f"materials manifest not found: {man_path}")
        actual_sha = sha_file(man_path)
        expected_sha = entry.get("manifest_sha256")
        if expected_sha and actual_sha != expected_sha:
            raise SystemExit(f"manifest sha mismatch for {mat_dir}: got={actual_sha} expected={expected_sha}")
        label = prefix or f"m{idx}"
        manifest_shas[label] = actual_sha
        man = json.loads(man_path.read_text(encoding="utf-8"))
        by_orig = {s["set"]: s for s in man["sets"]}
        wanted = list(entry.get("sets") or [s["set"] for s in man["sets"]])
        for orig_set in wanted:
            if orig_set not in by_orig:
                raise SystemExit(f"set {orig_set!r} not found in {man_path}")
            s = by_orig[orig_set]
            qid = f"{prefix}-{orig_set}" if prefix else orig_set
            if qid in sets_meta:
                raise SystemExit(f"duplicate qualified set id {qid!r}")
            # Strictly strip truth: runner never passes truth to agent or flagger.
            safe_claims = [
                {
                    "id": str(c["id"]),
                    "entity": str(c.get("entity") or ""),
                    "label": str(c.get("label") or ""),
                    "template_line": str(c["template_line"]),
                }
                for c in s["claims"]
            ]
            sets_meta[qid] = {
                "set_id": qid,
                "orig_set": orig_set,
                "prefix": prefix,
                "mat_dir": mat_dir,
                "domain": str(s.get("domain") or ""),
                "pages": list(s.get("pages") or [f"p{i}.html" for i in range(1, 6)]),
                "index": s.get("index"),
                "claims": safe_claims,
            }
    return sets_meta, manifest_shas


def _providers_from_plan(plan: dict[str, Any], all_sets: list[str]) -> list[dict[str, Any]]:
    """Normalize provider specifications from either `plan['providers']` or `plan['model']`."""
    raw = plan.get("providers")
    if isinstance(raw, list) and raw:
        out = []
        covered: set[str] = set()
        for idx, p in enumerate(raw):
            pset = list(p.get("sets") or all_sets)
            out.append({
                "name": str(p.get("name") or f"p{idx}"),
                "provider": str(p["provider"]),
                "model": str(p["model"]),
                "jobs": int(p.get("jobs") or plan.get("jobs") or 1),
                "sets": pset,
                "health_url": p.get("health_url"),
                "health_contains": p.get("health_contains"),
                "agent": str(p.get("agent") or (plan.get("model") or {}).get("agent") or "pi"),
                "max_turns": p.get("max_turns", (plan.get("model") or {}).get("max_turns")),
            })
            covered.update(pset)
        missing = [s for s in all_sets if s not in covered]
        if missing:
            raise SystemExit(f"sets not assigned to any provider: {missing[:5]}")
        return out

    m = plan.get("model") or {}
    return [{
        "name": str(m.get("name") or m.get("provider") or "default"),
        "provider": str(m.get("provider") or "fake"),
        "model": str(m.get("model") or "fake"),
        "jobs": int(plan.get("jobs") or 1),
        "sets": list(all_sets),
        "health_url": m.get("health_url"),
        "health_contains": m.get("health_contains"),
        "agent": str(m.get("agent") or "pi"),
        "max_turns": m.get("max_turns"),
    }]


def _merge_usage(usages: list[dict[str, Any] | None]) -> dict[str, Any]:
    keys = ("calls", "errors", "input", "output", "cache_creation_input_tokens", "cache_read_input_tokens")
    out: dict[str, Any] = {}
    for k in keys:
        vals = [u.get(k) for u in usages if isinstance(u, dict) and u.get(k) is not None]
        out[k] = sum(int(v) for v in vals) if vals else None
    return out


class ExpTRun:
    def __init__(
        self,
        plan_path: pathlib.Path,
        root: pathlib.Path,
        *,
        fake: bool = False,
        fake_agent_path: pathlib.Path | None = None,
        provider_filter: str | None = None,
    ):
        self.plan_path = plan_path
        self.plan = json.loads(plan_path.read_text(encoding="utf-8"))
        self.root = root
        self.fake = fake
        self.fake_agent_path = fake_agent_path or (HERE / "fake_agent.py")
        self.provider_filter = provider_filter

        self.sets_meta, self.manifest_shas = load_materials_specs(self.plan)
        self.all_sets = list(self.sets_meta.keys())
        self.providers = _providers_from_plan(self.plan, self.all_sets)
        if self.provider_filter:
            self.providers = [p for p in self.providers if p["name"] == self.provider_filter or p["provider"] == self.provider_filter]
            if not self.providers:
                raise SystemExit(f"no provider matched --provider {self.provider_filter!r}")

        self.arms = list(self.plan.get("arms") or FB.EXPT_ARMS)
        for a in self.arms:
            if a not in FB.EXPT_ARMS:
                raise SystemExit(f"unsupported Experiment T arm: {a!r}")
        self.reps = int(self.plan.get("reps") or 2)
        self.max_rounds = int(self.plan.get("max_rounds") if self.plan.get("max_rounds") is not None else 2)
        self.agent_timeout_s = int(self.plan.get("agent_timeout_s") or 600)
        self.budget_s = float(self.plan.get("budget_s") or (self.agent_timeout_s * (1 + self.max_rounds)))
        self.max_infra_retries = int(self.plan.get("max_infra_retries") or 2)

        self.routes = root / "routes.json"
        self.routes_meta = root / "routes_meta.json"
        self.stop = threading.Event()
        self.procs: set[subprocess.Popen] = set()
        self._egress: dict[str, tuple[subprocess.Popen, int]] = {}
        self._egress_lock = threading.Lock()
        self._server_port: int | None = None
        atexit.register(self._stop_all_egress)

    # ---------- logging & routing ----------
    def log(self, msg: str) -> None:
        line = f"{now_iso()} {msg}"
        with LOCK:
            print(line, flush=True)
            with open(self.root / "runner.log", "a", encoding="utf-8") as fh:
                fh.write(line + "\n")

    def host_for(self, set_id: str, rep: int) -> str:
        safe = re.sub(r"[^a-z0-9-]+", "-", set_id.lower()).strip("-")
        return f"{safe}-r{rep}.d2-sources.example"

    def urls_for(self, set_id: str, rep: int) -> list[str]:
        host = self.host_for(set_id, rep)
        return [f"http://{host}/{pg}" for pg in self.sets_meta[set_id]["pages"]]

    def index_url_for(self, set_id: str, rep: int) -> str | None:
        ix = self.sets_meta[set_id].get("index")
        return f"http://{self.host_for(set_id, rep)}/{ix}" if ix else None

    def write_prompt(self, set_id: str, rep: int) -> str:
        ix = self.index_url_for(set_id, rep)
        if ix:
            txt = PROMPTS["write_idx"].format(index=ix)
        else:
            txt = PROMPTS["write"].format(urls=" ".join(self.urls_for(set_id, rep)))
        if self.plan.get("no_tool_mention"):
            txt = re.sub(r" \(read them with curl -s\)| Read pages with curl -s\.| with curl -s", "", txt)
        return txt

    def set_route(self, host: str, site: pathlib.Path, *, arm: str, rep: int, round_idx: int) -> None:
        with LOCK:
            r = json.loads(self.routes.read_text(encoding="utf-8")) if self.routes.exists() else {}
            r[host] = str(site)
            meta = json.loads(self.routes_meta.read_text(encoding="utf-8")) if self.routes_meta.exists() else {}
            meta[host] = {"arm": arm, "cycle": 0, "rep": rep, "round": round_idx}
            tm = self.routes_meta.with_suffix(".tmp")
            tm.write_text(json.dumps(meta, indent=1), encoding="utf-8")
            os.replace(tm, self.routes_meta)
            tmp = self.routes.with_suffix(".tmp")
            tmp.write_text(json.dumps(r, indent=1), encoding="utf-8")
            os.replace(tmp, self.routes)

    def live_dir(self, set_id: str, rep: int) -> pathlib.Path:
        key = f"{set_id}_r{rep}"
        pl = self.plan.get("private_live")
        if not pl or self.fake:
            return self.root / "live" / key
        base = pathlib.Path(os.path.expandvars(os.path.expanduser(str(pl))))
        base.mkdir(parents=True, exist_ok=True)
        os.chmod(base, 0o711)
        sec = self.root / ".live_secret"
        with LOCK:
            if not sec.exists():
                sec.write_text(secrets.token_hex(32), encoding="utf-8")
                os.chmod(sec, 0o600)
            raw_sec = sec.read_text(encoding="utf-8").strip()
        tok = hmac.new(bytes.fromhex(raw_sec), key.encode("utf-8"), "sha256").hexdigest()[:24]
        return base / tok

    def vacant_python(self) -> str:
        vp = self.plan.get("vacant_python")
        if vp and not self.fake:
            return os.path.expandvars(os.path.expanduser(str(vp)))
        return sys.executable

    def _agent_env_base(self, live: pathlib.Path, prov: dict[str, Any]) -> dict[str, str]:
        port = self._server_port
        assert port is not None
        env = {
            k: v for k, v in os.environ.items()
            if not k.lower().endswith("_proxy") and not k.startswith("D2_")
        }
        # Always keep localhost/127.0.0.1 direct so local vLLM / LM Studio endpoints never traverse source proxy.
        no_proxy_parts = [x for x in ["localhost", "127.0.0.1", *NO_PROXY.split(",")] if x]
        no_proxy_val = ",".join(dict.fromkeys(no_proxy_parts))
        if prov["agent"] == "claude":
            env.update({
                "VACANT_HOME": str(live / "vh"),
                "http_proxy": f"http://127.0.0.1:{port}",
                "HTTP_PROXY": f"http://127.0.0.1:{port}",
                "no_proxy": CLAUDE_NO_PROXY,
                "NO_PROXY": CLAUDE_NO_PROXY,
                "TMPDIR": str(live / "tmp"),
                "DISABLE_TELEMETRY": "1",
                "DISABLE_ERROR_REPORTING": "1",
                "DISABLE_AUTOUPDATER": "1",
                "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
                "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1",
            })
            return env
        env.update({
            "PI_CODING_AGENT_DIR": str(live / "cfg"),
            "VACANT_HOME": str(live / "vh"),
            "PI_SKIP_VERSION_CHECK": "1",
            "http_proxy": f"http://127.0.0.1:{port}",
            "HTTP_PROXY": f"http://127.0.0.1:{port}",
            "no_proxy": no_proxy_val,
            "NO_PROXY": no_proxy_val,
            "TMPDIR": str(live / "tmp"),
        })
        if self.fake:
            # Ensure vacant_network is importable when fake mode uses current repo python.
            existing_pp = env.get("PYTHONPATH", "")
            env["PYTHONPATH"] = f"{REPO}:{existing_pp}" if existing_pp else str(REPO)
        return env

    def ensure_egress(self, live: pathlib.Path, prov: dict[str, Any]) -> int:
        key = str(live)
        with self._egress_lock:
            cur = self._egress.get(key)
            if cur and cur[0].poll() is None:
                return cur[1]
        ready = live / "egress.ready"
        ready.unlink(missing_ok=True)
        env = self._agent_env_base(live, prov)
        env.pop("PI_CODING_AGENT_DIR", None)
        py = self.vacant_python()
        cmd = [py]
        if not self.fake:
            cmd.append("-I")
        cmd += [
            "-m", "vacant_network", "trace", "egress",
            "--port", "0",
            "--upstream-proxy", f"http://127.0.0.1:{self._server_port}",
            "--ready-file", str(ready),
        ]
        err_fh = open(live / "egress.err", "a", encoding="utf-8")
        proc = subprocess.Popen(
            cmd,
            cwd=live / "ws",
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=err_fh,
            start_new_session=True,
        )
        err_fh.close()
        port = None
        for _ in range(150):
            if proc.poll() is not None:
                break
            try:
                port = int(json.loads(ready.read_text(encoding="utf-8"))["port"])
                break
            except (OSError, ValueError, KeyError):
                time.sleep(0.1)
        if port is None:
            self._kill(proc)
            raise InfraError(f"egress proxy did not start for {live}")
        with self._egress_lock:
            self._egress[key] = (proc, port)
        return port

    def stop_egress(self, live: pathlib.Path) -> None:
        key = str(live)
        with self._egress_lock:
            pr = self._egress.pop(key, None)
        if pr:
            self._kill(pr[0])

    def _stop_all_egress(self) -> None:
        with self._egress_lock:
            items = list(self._egress.values())
            self._egress.clear()
        for proc, _ in items:
            self._kill(proc)

    def agent_env(self, live: pathlib.Path, prov: dict[str, Any], *, for_agent: bool = True) -> dict[str, str]:
        env = self._agent_env_base(live, prov)
        if for_agent and self.plan.get("egress", True):
            port = self.ensure_egress(live, prov)
            env["http_proxy"] = f"http://127.0.0.1:{port}"
            env["HTTP_PROXY"] = f"http://127.0.0.1:{port}"
        return env

    def _agent_argv(self, live: pathlib.Path, prov: dict[str, Any], prompt: str, out: pathlib.Path) -> list[str]:
        if self.fake:
            return [sys.executable, str(self.fake_agent_path), prompt]
        if prov["agent"] == "claude":
            settings = live / "cfg" / "settings.json"
            if not settings.is_file():
                settings = live / "cfg" / ".claude" / "settings.json"
            argv = [
                "claude", "-p",
                "--model", prov["model"],
                "--output-format", "stream-json", "--verbose",
                "--setting-sources", "",
                "--settings", str(settings),
                "--strict-mcp-config",
                "--disable-slash-commands",
                "--no-session-persistence",
                "--permission-mode", "dontAsk",
                "--allowedTools", CLAUDE_ALLOWED_TOOLS,
                "--disallowedTools", CLAUDE_DISALLOWED_TOOLS,
            ]
            if prov.get("max_turns") is not None:
                argv += ["--max-turns", str(prov["max_turns"])]
            argv += ["--", prompt]
            return argv
        return [
            "pi", "-p", "--mode", "json",
            "--session-dir", str(out / "sessions"),
            "--provider", prov["provider"],
            "--model", prov["model"],
            prompt,
        ]

    def _kill(self, pr: subprocess.Popen) -> None:
        if pr.poll() is not None:
            return
        for sig in (signal.SIGTERM, signal.SIGKILL):
            try:
                os.killpg(pr.pid, sig)
            except ProcessLookupError:
                return
            except PermissionError:
                try:
                    pr.send_signal(sig)
                except OSError:
                    return
            try:
                pr.wait(timeout=10)
                return
            except subprocess.TimeoutExpired:
                continue

    def run_agent(
        self,
        live: pathlib.Path,
        prov: dict[str, Any],
        prompt: str,
        out: pathlib.Path,
        *,
        timeout_s: float,
    ) -> dict[str, Any]:
        out.mkdir(parents=True, exist_ok=True)
        (out / "prompt.txt").write_text(prompt, encoding="utf-8")
        t0 = time.time()
        argv = self._agent_argv(live, prov, prompt, out)
        env = self.agent_env(live, prov, for_agent=True)
        rc: int | str | None = None
        with open(out / "agent.log", "w", encoding="utf-8") as lf:
            pr = subprocess.Popen(
                argv,
                cwd=live / "ws",
                env=env,
                stdout=lf,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
            )
            with LOCK:
                self.procs.add(pr)
            try:
                rc = pr.wait(timeout=max(1.0, float(timeout_s)))
            except subprocess.TimeoutExpired:
                rc = "timeout"
                self._kill(pr)
            finally:
                with LOCK:
                    self.procs.discard(pr)
        wall_s = round(time.time() - t0, 3)
        if self.fake:
            u = {"calls": 1, "errors": 0, "input": len(prompt), "output": 100}
        elif prov["agent"] == "claude":
            u = usage_from_claude_log(out / "agent.log")
        else:
            u = usage_from_log(out / "agent.log")
        res = {"rc": rc, "wall_s": wall_s, "usage": u, "t_start": t0, "t_end": time.time()}
        write_json(out / "run.json", res)
        if not self.fake and (u is None or (u.get("calls") == 0 and u.get("errors"))):
            raise InfraError(f"infra: {out} usage={u}")
        return res

    def _checkpoint_and_ingest(self, live: pathlib.Path, label: str) -> tuple[Any, int]:
        """Ensure Vacant Recorder exists, ingest egress fetches, checkpoint workspace, return (rec, last_seq)."""
        rec = FB.open_recorder(live / "vh", live / "ws")
        assert rec is not None
        S.ingest_egress(rec)
        rec.checkpoint(label)
        evts = rec.events()
        last_seq = max((int(e.get("seq") or 0) for e in evts), default=0)
        return rec, last_seq

    def _setup_live_fresh(self, live: pathlib.Path, set_id: str) -> None:
        self.stop_egress(live)
        if live.exists():
            rmtree_retry(live)
        for d in ("ws", "vh/adapters", "cfg", "tmp"):
            (live / d).mkdir(parents=True, exist_ok=True)
        meta = self.sets_meta[set_id]
        shutil.copy(meta["mat_dir"] / "sets" / meta["orig_set"] / "template.md", live / "ws" / "report.md")
        shutil.copytree(meta["mat_dir"] / "sets" / meta["orig_set"] / "cycle_0" / "site", live / "site")
        if not self.fake:
            acfg = self.plan.get("agentcfg") or {}
            if acfg.get("dir"):
                cfg_dir = pathlib.Path(os.path.expandvars(os.path.expanduser(str(acfg["dir"]))))
                for f in acfg.get("copy") or []:
                    src = cfg_dir / f
                    if src.exists():
                        (shutil.copytree if src.is_dir() else shutil.copy2)(src, live / "cfg" / f)
            if acfg.get("install_json"):
                ij = pathlib.Path(os.path.expandvars(os.path.expanduser(str(acfg["install_json"]))))
                if ij.is_file():
                    shutil.copy2(ij, live / "vh" / "adapters" / "install.json")

    def _restore_c0_snapshot(self, live: pathlib.Path, snap: pathlib.Path) -> None:
        self.stop_egress(live)
        for d in ("ws", "vh"):
            dst = live / d
            if dst.exists():
                rmtree_retry(dst)
            shutil.copytree(snap / d, dst, symlinks=True)

    # ---------- one (set, rep) ----------
    def do_set_rep(self, set_id: str, rep: int, arms: list[str], prov: dict[str, Any]) -> None:
        live = self.live_dir(set_id, rep)
        try:
            self._do_set_rep(live, set_id, rep, arms, prov)
        finally:
            self.stop_egress(live)

    def _do_set_rep(
        self,
        live: pathlib.Path,
        set_id: str,
        rep: int,
        arms: list[str],
        prov: dict[str, Any],
    ) -> None:
        meta = self.sets_meta[set_id]
        claims = meta["claims"]
        host = self.host_for(set_id, rep)
        rdir = self.root / "cells" / set_id / f"r{rep}"
        c0_dir = rdir / "c0"
        snap = c0_dir / "snapshot"

        # 1) Cycle-0 draft (shared starting point for A, G, T, T0 within this (set, rep))
        if not (c0_dir / "done.json").exists():
            c0_err: Exception | None = None
            for attempt in range(self.max_infra_retries + 1):
                try:
                    self._setup_live_fresh(live, set_id)
                    self.set_route(host, live / "site", arm="c0", rep=rep, round_idx=0)
                    rec0 = FB.open_recorder(live / "vh", live / "ws")
                    assert rec0 is not None
                    rec0.checkpoint("c0_start")
                    wprompt = self.write_prompt(set_id, rep)
                    r0 = self.run_agent(live, prov, wprompt, c0_dir / "run", timeout_s=self.agent_timeout_s)
                    rec0, c0_seq = self._checkpoint_and_ingest(live, "c0_end")
                    c0_text = (live / "ws" / "report.md").read_text(encoding="utf-8", errors="replace")
                    c0_flags = FB.compute_flags_from_recorder(
                        rec0, c0_text, claims, round_idx=0, prev_values=None, prev_bound_seq=0,
                        cur_bound_seq=c0_seq, ingest_egress=False,
                    )
                    (c0_dir / "report.md").write_text(c0_text, encoding="utf-8")
                    write_json(c0_dir / "flags.json", c0_flags)
                    if snap.exists():
                        rmtree_retry(snap)
                    snap.mkdir(parents=True)
                    self.stop_egress(live)
                    for d in ("ws", "vh"):
                        shutil.copytree(live / d, snap / d, symlinks=True)
                    write_json(
                        c0_dir / "done.json",
                        {
                            **r0,
                            "chain_len": c0_seq,
                            "flagged_count": c0_flags["flagged_count"],
                            "flagged_ids": c0_flags["flagged_ids"],
                            "fetched_urls": c0_flags["fetched_urls"],
                            "provider": prov["provider"],
                            "model": prov["model"],
                            "ts": now_iso(),
                        },
                    )
                    self.log(
                        f"{set_id} r{rep} c0 rc={r0['rc']} wall={r0['wall_s']}s "
                        f"flagged={c0_flags['flagged_count']}/{len(claims)}"
                    )
                    c0_err = None
                    break
                except InfraError as exc:
                    c0_err = exc
                    self.log(f"{set_id} r{rep} c0 INFRA attempt={attempt + 1}: {exc}")
            if c0_err is not None:
                write_json(c0_dir / "done.json", {"infra_void": True, "error": str(c0_err), "ts": now_iso()})
                for arm in arms:
                    adir = rdir / arm
                    if not (adir / "done.json").exists():
                        write_json(
                            adir / "cell.json",
                            {
                                "set": set_id, "rep": rep, "arm": arm,
                                "infra_void": True, "error": f"c0 infra_void: {c0_err}",
                                "provider": prov["provider"], "model": prov["model"],
                            },
                        )
                        write_json(adir / "done.json", {"infra_void": True, "ts": now_iso()})
                return

        c0_done = json.loads((c0_dir / "done.json").read_text(encoding="utf-8"))
        if c0_done.get("infra_void"):
            for arm in arms:
                adir = rdir / arm
                if not (adir / "done.json").exists():
                    write_json(
                        adir / "cell.json",
                        {
                            "set": set_id, "rep": rep, "arm": arm,
                            "infra_void": True, "error": c0_done.get("error", "c0 infra_void"),
                            "provider": prov["provider"], "model": prov["model"],
                        },
                    )
                    write_json(adir / "done.json", {"infra_void": True, "ts": now_iso()})
            return

        c0_flags_initial = json.loads((c0_dir / "flags.json").read_text(encoding="utf-8"))
        c0_text = (c0_dir / "report.md").read_text(encoding="utf-8")
        c0_seq = int(c0_done.get("chain_len") or 0)
        c0_wall = float(c0_done.get("wall_s") or 0.0)

        # Ensure live/site exists if resuming after c0
        if not (live / "site").exists():
            (live / "site").parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(meta["mat_dir"] / "sets" / meta["orig_set"] / "cycle_0" / "site", live / "site")
            if not self.fake:
                (live / "cfg").mkdir(parents=True, exist_ok=True)
                (live / "tmp").mkdir(parents=True, exist_ok=True)
                acfg = self.plan.get("agentcfg") or {}
                if acfg.get("dir"):
                    cfg_dir = pathlib.Path(os.path.expandvars(os.path.expanduser(str(acfg["dir"]))))
                    for f in acfg.get("copy") or []:
                        src = cfg_dir / f
                        dst = live / "cfg" / f
                        if src.exists() and not dst.exists():
                            (shutil.copytree if src.is_dir() else shutil.copy2)(src, dst)

        # 2) Run each arm from the exact same c0 snapshot
        for arm in arms:
            if self.stop.is_set():
                return
            adir = rdir / arm
            if (adir / "done.json").exists():
                continue
            self._run_arm_cell(
                live=live,
                snap=snap,
                adir=adir,
                set_id=set_id,
                rep=rep,
                arm=arm,
                host=host,
                claims=claims,
                prov=prov,
                c0_done=c0_done,
                c0_text=c0_text,
                c0_seq=c0_seq,
                c0_wall=c0_wall,
                c0_flags=c0_flags_initial,
            )

    def _run_arm_cell(
        self,
        *,
        live: pathlib.Path,
        snap: pathlib.Path,
        adir: pathlib.Path,
        set_id: str,
        rep: int,
        arm: str,
        host: str,
        claims: list[dict[str, Any]],
        prov: dict[str, Any],
        c0_done: dict[str, Any],
        c0_text: str,
        c0_seq: int,
        c0_wall: float,
        c0_flags: dict[str, Any],
    ) -> None:
        cell_err: Exception | None = None
        for attempt in range(self.max_infra_retries + 1):
            if adir.exists():
                rmtree_retry(adir)
            adir.mkdir(parents=True, exist_ok=True)
            self._restore_c0_snapshot(live, snap)

            ident = Identity.generate()
            book = Logbook()
            chain_path = adir / "feedback_chain.ndjson"

            rounds_meta: list[dict[str, Any]] = []
            extra_usages: list[dict[str, Any] | None] = []
            extra_wall_s = 0.0
            stop_reason = "native_c0"
            cur_flags = c0_flags
            prev_values = dict(c0_flags["values"])
            prev_seq = c0_seq
            cur_seq = c0_seq
            t_arm_start = time.time()

            try:
                if arm == "A":
                    ev = FB.make_trigger_evidence("A", 0, c0_flags)
                    FB.feedback_event(
                        book, ident, arm="A", round_idx=0, decision="native_c0",
                        feedback_text=None, evidence=ev,
                    )
                    stop_reason = "native_c0"
                else:
                    for r_idx in range(1, self.max_rounds + 1):
                        if self.stop.is_set():
                            return
                        # Decide whether to send feedback and run round r_idx
                        if arm == "G":
                            fb_text = FB.build_G_feedback()
                            ev = FB.make_trigger_evidence("G", r_idx - 1, None)
                        else:
                            fb_text = FB.build_arm_feedback(arm, cur_flags)
                            ev = FB.make_trigger_evidence(arm, r_idx - 1, cur_flags)

                        if fb_text is None:
                            stop_reason = "stop_no_flags"
                            FB.feedback_event(
                                book, ident, arm=arm, round_idx=r_idx, decision="stop_no_flags",
                                feedback_text=None, evidence=ev,
                            )
                            break

                        rem_budget = self.budget_s - (c0_wall + extra_wall_s)
                        if rem_budget <= 1.0:
                            stop_reason = "stop_budget"
                            FB.feedback_event(
                                book, ident, arm=arm, round_idx=r_idx, decision="stop_budget",
                                feedback_text=None, evidence=ev,
                                extra={"remaining_budget_s": round(rem_budget, 3)},
                            )
                            break

                        FB.feedback_event(
                            book, ident, arm=arm, round_idx=r_idx, decision="send_feedback",
                            feedback_text=fb_text, evidence=ev,
                        )
                        FB.save_feedback_chain(book, ident, chain_path)

                        r_out = adir / f"round_{r_idx}"
                        r_out.mkdir(parents=True, exist_ok=True)
                        (r_out / "feedback.txt").write_text(fb_text, encoding="utf-8")
                        self.set_route(host, live / "site", arm=arm, rep=rep, round_idx=r_idx)
                        run_timeout = min(float(self.agent_timeout_s), rem_budget)
                        rr = self.run_agent(live, prov, fb_text, r_out / "run", timeout_s=run_timeout)
                        extra_wall_s = round(extra_wall_s + float(rr.get("wall_s") or 0.0), 3)
                        extra_usages.append(rr.get("usage"))

                        rec, new_seq = self._checkpoint_and_ingest(live, f"expT_{arm}_r{r_idx}")
                        post_text = (live / "ws" / "report.md").read_text(encoding="utf-8", errors="replace")
                        (r_out / "report.md").write_text(post_text, encoding="utf-8")
                        post_flags = FB.compute_flags_from_recorder(
                            rec, post_text, claims,
                            round_idx=r_idx,
                            prev_values=prev_values,
                            prev_bound_seq=prev_seq,
                            cur_bound_seq=new_seq,
                            ingest_egress=False,
                        )
                        write_json(r_out / "flags.json", post_flags)
                        r_info = {
                            "round": r_idx,
                            "trigger_flagged_ids": ev.get("flagged_ids", []),
                            "trigger_flagged_count": ev.get("flagged_count", 0),
                            "post_flagged_ids": post_flags["flagged_ids"],
                            "post_flagged_count": post_flags["flagged_count"],
                            "post_fetched_urls": post_flags["fetched_urls"],
                            "round_fetch_count": post_flags["round_fetch_count"],
                            "agent": rr,
                            "chain_len": new_seq,
                        }
                        write_json(r_out / "round.json", r_info)
                        rounds_meta.append(r_info)

                        prev_values = dict(post_flags["values"])
                        prev_seq = new_seq
                        cur_seq = new_seq
                        cur_flags = post_flags
                    else:
                        # Completed max_rounds without early stop
                        if arm == "G":
                            final_ev = FB.make_trigger_evidence("G", self.max_rounds, None)
                            stop_reason = "stop_max_rounds"
                        else:
                            final_ev = FB.make_trigger_evidence(arm, self.max_rounds, cur_flags)
                            stop_reason = "stop_no_flags" if cur_flags["flagged_count"] == 0 else "stop_max_rounds"
                        FB.feedback_event(
                            book, ident, arm=arm, round_idx=self.max_rounds,
                            decision=stop_reason, feedback_text=None, evidence=final_ev,
                        )

                FB.save_feedback_chain(book, ident, chain_path)
                final_text = (live / "ws" / "report.md").read_text(encoding="utf-8", errors="replace")
                (adir / "report.md").write_text(final_text, encoding="utf-8")
                self.stop_egress(live)
                fin = adir / "final"
                for d in ("ws", "vh"):
                    shutil.copytree(live / d, fin / d, symlinks=True)

                c0_usage = c0_done.get("usage")
                total_usage = _merge_usage([c0_usage, *extra_usages])
                extra_usage = _merge_usage(extra_usages) if extra_usages else {
                    "calls": 0, "errors": 0, "input": 0, "output": 0,
                    "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0,
                }
                cell_doc = {
                    "schema": "vacant.d2.expT.cell/1",
                    "set": set_id,
                    "orig_set": self.sets_meta[set_id]["orig_set"],
                    "domain": self.sets_meta[set_id]["domain"],
                    "rep": rep,
                    "arm": arm,
                    "provider": prov["provider"],
                    "model": prov["model"],
                    "infra_void": False,
                    "rounds_run": len(rounds_meta),
                    "max_rounds": self.max_rounds,
                    "stop_reason": stop_reason,
                    "c0_wall_s": c0_wall,
                    "extra_wall_s": extra_wall_s,
                    "total_wall_s": round(c0_wall + extra_wall_s, 3),
                    "arm_wall_s": round(time.time() - t_arm_start, 3),
                    "c0_usage": c0_usage,
                    "extra_usage": extra_usage,
                    "total_usage": total_usage,
                    "c0_flagged_ids": c0_flags["flagged_ids"],
                    "c0_flagged_count": c0_flags["flagged_count"],
                    "final_flagged_ids": cur_flags["flagged_ids"],
                    "final_flagged_count": cur_flags["flagged_count"],
                    "rounds": rounds_meta,
                    "chain_len": cur_seq,
                    "feedback_chain_sha256": sha_file(chain_path),
                    "ts": now_iso(),
                }
                write_json(adir / "cell.json", cell_doc)
                write_json(adir / "done.json", {"ts": now_iso(), "stop_reason": stop_reason, "rounds_run": len(rounds_meta)})
                self.log(
                    f"{set_id} r{rep} {arm} rounds={len(rounds_meta)} stop={stop_reason} "
                    f"flagged={c0_flags['flagged_count']}->{cur_flags['flagged_count']} "
                    f"wall={cell_doc['total_wall_s']}s"
                )
                cell_err = None
                break
            except InfraError as exc:
                cell_err = exc
                self.log(f"{set_id} r{rep} {arm} INFRA attempt={attempt + 1}: {exc}")

        if cell_err is not None:
            write_json(
                adir / "cell.json",
                {
                    "schema": "vacant.d2.expT.cell/1",
                    "set": set_id,
                    "orig_set": self.sets_meta[set_id]["orig_set"],
                    "domain": self.sets_meta[set_id]["domain"],
                    "rep": rep,
                    "arm": arm,
                    "provider": prov["provider"],
                    "model": prov["model"],
                    "infra_void": True,
                    "error": str(cell_err),
                    "ts": now_iso(),
                },
            )
            write_json(adir / "done.json", {"infra_void": True, "error": str(cell_err), "ts": now_iso()})

    # ---------- batch lifecycle ----------
    def _pick_free_port(self) -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            return int(s.getsockname()[1])

    def start_server(self) -> subprocess.Popen:
        cfg_port = int((self.plan.get("server") or {}).get("port") or 0)
        port = cfg_port if cfg_port > 0 else self._pick_free_port()
        self._server_port = port
        err_fh = open(self.root / "server.err", "a", encoding="utf-8")
        srv = subprocess.Popen(
            [
                sys.executable, str(HERE / "source_server.py"),
                "--port", str(port),
                "--routes", str(self.routes),
                "--log", str(self.root / "access.jsonl"),
                "--meta", str(self.routes_meta),
            ],
            stdout=subprocess.DEVNULL,
            stderr=err_fh,
            start_new_session=True,
        )
        err_fh.close()
        for _ in range(50):
            try:
                socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
                return srv
            except OSError:
                time.sleep(0.1)
        self._kill(srv)
        raise SystemExit(f"source server did not start on port {port}")

    def check_provider_health(self, prov: dict[str, Any]) -> None:
        if self.fake or not prov.get("health_url"):
            return
        url = str(prov["health_url"])
        need = str(prov.get("health_contains") or "")
        op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            with op.open(url, timeout=10) as r:
                body = r.read(200_000).decode("utf-8", "replace")
            if need and need not in body:
                raise SystemExit(f"health check {url} missing {need!r}")
        except Exception as exc:
            raise SystemExit(f"health check failed for {prov['name']} ({url}): {exc}") from exc

    def code_state(self) -> dict[str, Any]:
        def git(*a: str) -> str:
            try:
                return subprocess.run(["git", *a], cwd=REPO, capture_output=True, text=True).stdout.strip()
            except OSError:
                return ""
        files = [
            "ops/d2/run_expT.py", "ops/d2/expT_feedback.py", "ops/d2/expT_metrics.py",
            "ops/d2/source_server.py", "ops/d2/score_d2.py",
        ]
        return {
            "head": git("rev-parse", "HEAD"),
            "script_sha256": {f: sha_file(REPO / f) for f in files if (REPO / f).exists()},
        }

    def go(self) -> int:
        self.root.mkdir(parents=True, exist_ok=True)
        self._lockf = open(self.root / ".runner.lock", "w", encoding="utf-8")
        try:
            fcntl.flock(self._lockf, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise SystemExit(f"refusing: another runner holds {self.root / '.runner.lock'}")

        for prov in self.providers:
            self.check_provider_health(prov)

        runj = self.root / "RUN.json"
        plan_sha = sha_file(self.plan_path)
        if runj.exists():
            old = json.loads(runj.read_text(encoding="utf-8"))
            if old["plan_sha256"] != plan_sha:
                raise SystemExit("this root was started with a different plan")
            old.setdefault("resumes", []).append({"ts": now_iso(), **self.code_state()})
            write_json(runj, old)
        else:
            write_json(
                runj,
                {
                    "schema": "vacant.d2.expT.run/1",
                    "plan": str(self.plan_path),
                    "plan_sha256": plan_sha,
                    "plan_body": self.plan,
                    "manifest_sha256": self.manifest_shas,
                    "runner_sha256": sha_file(pathlib.Path(__file__)),
                    "started": now_iso(),
                    "fake": self.fake,
                    **self.code_state(),
                },
            )

        srv = self.start_server()
        rng = random.Random(int(self.plan.get("seed") or 20261127))
        arm_orders: dict[str, list[str]] = {}
        for sid in self.all_sets:
            for rep in range(1, self.reps + 1):
                o = list(self.arms)
                rng.shuffle(o)
                arm_orders[f"{sid}/r{rep}"] = o
        write_json(self.root / "arm_orders.json", arm_orders)

        errors: list[tuple[str, int, str]] = []
        threads: list[threading.Thread] = []

        def make_worker(prov: dict[str, Any], queue: list[tuple[str, int]]):
            qlock = threading.Lock()

            def _run():
                while not self.stop.is_set():
                    with qlock:
                        if not queue:
                            return
                        sid, rep = queue.pop(0)
                    try:
                        self.do_set_rep(sid, rep, arm_orders[f"{sid}/r{rep}"], prov)
                    except Exception as exc:  # noqa: BLE001
                        with LOCK:
                            errors.append((sid, rep, repr(exc)))
                        self.log(f"{sid} r{rep} ERROR {exc!r}")
            return _run

        def _term(*_):
            self.stop.set()
            with LOCK:
                ps = list(self.procs)
            for pr in ps:
                self._kill(pr)

        if threading.current_thread() is threading.main_thread():
            signal.signal(signal.SIGTERM, _term)
            signal.signal(signal.SIGINT, _term)

        for prov in self.providers:
            q = [(sid, rep) for sid in prov["sets"] for rep in range(1, self.reps + 1)]
            wfn = make_worker(prov, q)
            for _ in range(max(1, int(prov["jobs"]))):
                t = threading.Thread(target=wfn, daemon=True)
                threads.append(t)
                t.start()

        for t in threads:
            while t.is_alive():
                t.join(timeout=1.0)

        self._stop_all_egress()
        self._kill(srv)
        self.log(f"batch end; errors={errors}; stopped={self.stop.is_set()}")
        return 1 if errors else (130 if self.stop.is_set() else 0)


def main() -> int:
    ap = argparse.ArgumentParser(description="Experiment T runner (cycle 0 revision loop).")
    sp = ap.add_subparsers(dest="cmd", required=True)
    r = sp.add_parser("run", help="Execute an Experiment T plan")
    r.add_argument("--plan", required=True)
    r.add_argument("--root", required=True)
    r.add_argument("--fake", action="store_true", help="Run with fake agent (offline selftest)")
    r.add_argument("--fake-agent", help="Optional custom fake agent script path (implies --fake)")
    r.add_argument("--provider", help="Optional single provider name to run from a multi-provider plan")
    r.add_argument(
        "--allow-uncommitted-plan",
        action="store_true",
        help="Skip git cleanliness check (for Colab git-archive VMs or smoke tests)",
    )
    a = ap.parse_args()
    plan = pathlib.Path(a.plan).resolve()
    is_fake = bool(a.fake or a.fake_agent)
    if not is_fake and not a.allow_uncommitted_plan and (REPO / ".git").exists():
        try:
            rel = plan.relative_to(REPO)
            dirty = subprocess.run(
                ["git", "status", "--porcelain", "--", str(rel), "ops/d2", "vacant_network"],
                cwd=REPO, capture_output=True, text=True,
            ).stdout.strip()
            if dirty:
                raise SystemExit(f"refusing: uncommitted changes:\n{dirty}")
        except ValueError:
            raise SystemExit(f"refusing: plan {plan} is outside repo (pass --allow-uncommitted-plan for smoke)")
    return ExpTRun(
        plan,
        pathlib.Path(a.root).expanduser().resolve(),
        fake=is_fake,
        fake_agent_path=pathlib.Path(a.fake_agent).resolve() if a.fake_agent else None,
        provider_filter=a.provider,
    ).go()


if __name__ == "__main__":
    raise SystemExit(main())
