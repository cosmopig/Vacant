"""twin/hooks_smoke — 一位合成分身在 VACANT_TWIN_HOOKS=1 下真跑一次，量掛鉤接上後的事實，再撤回。

在有 pi＋bwrap 的機器上（舊 VM）跑；環境變數由呼叫端給（VACANT_HOME、VACANT_TWIN_HOOKS=1、VACANT_TWIN_HOOK_EXT、
VACANT_TWIN_PI）。輸出一份 JSON：每跑秒數、trace 鏈驗章、儀表板看得到幾個專案、零設定檢查寫了什麼、
撤回前後 VACANT_HOME 裡有沒有分身寫的字。**特質是合成的**。
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time

HERE = pathlib.Path(__file__).resolve()
REPO = HERE.parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from ops.exhibit.twin import twin_hooks, twinagent, twinlink, twinvault  # noqa: E402
from ops.exhibit.twin.twinstore import KIND_SUBMITTED, TwinStore  # noqa: E402

CARD = {"need": "想把週末的時間安排得不那麼亂", "vibe": "慢熱、念舊、喜歡手寫",
        "first_line": "我先泡一壺茶再說。"}
TEXT = ("（合成的特質，不是真人）我做事慢，但答應的事一定做完。"
        "喜歡整理舊照片、會記得朋友的生日，最近覺得週末總是一下就過完了。")


def scan(root: pathlib.Path, needles: list[bytes]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {n.decode(): [] for n in needles}
    if not root.exists():
        return out
    for p in sorted(root.rglob("*")):
        if p.is_file() and not p.is_symlink():
            try:
                b = p.read_bytes()
            except OSError:
                continue
            for n in needles:
                if n in b:
                    out[n.decode()].append(str(p.relative_to(root)))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--endpoint", required=True)
    ap.add_argument("--model", default=twinlink.DEFAULT_MODEL)
    ap.add_argument("--out", required=True)
    ap.add_argument("--tmp", required=True)
    ap.add_argument("--sid", default="SYN-hooks-20261012")
    ap.add_argument("--timeout", type=float, default=twinagent.DEFAULT_AGENT_TIMEOUT)
    ap.add_argument("--enclose", default="on")
    ap.add_argument("--no-withdraw", action="store_true")
    a = ap.parse_args(argv)
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    tmp = pathlib.Path(a.tmp)
    tmp.mkdir(parents=True, exist_ok=True)
    db = tmp / "twinstore.sqlite3"
    events = tmp / "lifecycle.jsonl"
    home = twin_hooks.vacant_home()
    rep: dict = {"sid": a.sid, "hooks_enabled": twin_hooks.enabled(), "vacant_home": str(home),
                 "ext": str(twin_hooks.ext_path()), "encl_extras": twin_hooks.encl_extras()}
    st = TwinStore(db)
    payload, secs = st.vault.seal_card(a.sid, CARD, TEXT, ts=int(time.time() * 1000))
    twinvault.append_sealed(st, KIND_SUBMITTED, a.sid, payload, secs, source="smoke:synthetic", what="card")
    st.close()
    t0 = time.time()
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = twinlink.main(["--db", str(db), "generate", "--endpoint", a.endpoint, "--model", a.model,
                            "--engine", "agent", "--parallel", "1", "--agent-timeout", str(a.timeout),
                            "--events", str(events), "--enclose", a.enclose, "--require-tier", "B"])
    rep["generate_rc"] = rc
    rep["wall_s"] = round(time.time() - t0, 1)
    try:
        rep["generate"] = json.loads(buf.getvalue())
    except ValueError:
        rep["generate_raw"] = buf.getvalue()[-500:]
    work_root = twinagent.default_work_root(db)
    ws, rd = twinagent.paths_for(work_root, a.sid)
    st = TwinStore(db)
    tw = (st.current(a.sid) or {}).get("twin") or {}
    rep["twin"] = {k: tw.get(k) for k in ("engine", "degrade_kind", "decision", "stop_reason", "accepted",
                                          "requests_seen", "tier", "enclosed", "door_calls", "latency_ms")}
    st.close()
    rep["agent_stderr_tail"] = (rd / "agent_stderr.log").read_text(errors="replace")[-600:] \
        if (rd / "agent_stderr.log").is_file() else None
    env = {**os.environ, "PYTHONPATH": str(REPO)}
    # 追緝：鏈驗章、儀表板
    if home and home.is_dir():
        r = subprocess.run([sys.executable, "-m", "vacant_network", "trace", "verify"], cwd=str(ws), env=env,
                           capture_output=True, text=True, timeout=120) if ws.is_dir() else None
        rep["trace_verify"] = {"rc": r.returncode, "out": (r.stdout + r.stderr)[-300:]} if r else "no ws"
        r = subprocess.run([sys.executable, "-m", "vacant_network", "dashboard", "--json"], env=env,
                           capture_output=True, text=True, timeout=120)
        try:
            ov = json.loads(r.stdout)
            rep["dashboard"] = {"mode": (ov.get("install") or {}).get("mode"),
                                "agents": [(x["name"], x["health"]) for x in (ov.get("install") or {}).get("agents", [])],
                                "projects": ov.get("projects"),
                                "hooks_n": len((ov.get("hooks") or {}).get("events") or []),
                                "hooks_errors": (ov.get("hooks") or {}).get("errors")}
        except ValueError:
            rep["dashboard"] = {"error": (r.stdout + r.stderr)[-300:]}
        projs = sorted((home / "trace" / "projects").glob("*")) if (home / "trace" / "projects").is_dir() else []
        rep["project_dirs"] = [p.name for p in projs]
        rep["project_files"] = {p.name: sorted(x.name for x in p.iterdir()) for p in projs}
        for p in projs:
            pf = p / "perf.jsonl"
            if pf.is_file():
                rows = [json.loads(l) for l in pf.read_text().splitlines() if l.strip()]
                by: dict = {}
                for r_ in rows:
                    by.setdefault(r_.get("event"), []).append(float(r_.get("ms") or 0))
                rep.setdefault("hook_perf_ms", {})[p.name] = {
                    "n": len(rows), "total_ms": round(sum(float(r_.get("ms") or 0) for r_ in rows), 1),
                    "max_ms": max((float(r_.get("ms") or 0) for r_ in rows), default=0),
                    "by_event": {k: {"n": len(v), "sum": round(sum(v), 1), "max": max(v)} for k, v in by.items()}}
            pcl = rd / "hooks_postcheck.log"
            if pcl.is_file():
                rep["postcheck_log"] = pcl.read_text(errors="replace")[-300:]
            d = p / "delivery.md"
            if d.is_file():
                rep.setdefault("delivery_md", {})[p.name] = d.read_text(errors="replace")[:3000]
        # 撤回前殘留（正控制）：分身寫的字在 VACANT_HOME 裡找得到
        needles = [b"## ", TEXT.encode()[:30]]
        wsfiles = [f for f in ws.rglob("*") if f.is_file()] if ws.is_dir() else []
        letter = ws / "信.md"
        if letter.is_file():
            ln = [l for l in letter.read_text(errors="replace").splitlines() if len(l.strip()) >= 10]
            if ln:
                needles = [ln[0].strip()[:14].encode()]
        rep["marker"] = needles[0].decode(errors="replace")
        rep["scan_before"] = scan(home, needles)
    if not a.no_withdraw:
        st = TwinStore(db)
        w = twinlink.withdraw(st, a.sid, reason="smoke:withdraw")
        rep["withdraw"] = {k: w.get(k) for k in ("ok", "fully_erased", "run_artifacts_erased",
                                                 "run_artifacts_problems", "problems")}
        st.close()
        if home and home.is_dir():
            rep["scan_after"] = scan(home, needles)
            rep["project_dirs_after"] = [p.name for p in (home / "trace" / "projects").glob("*")] \
                if (home / "trace" / "projects").is_dir() else []
            rep["present_after"] = twin_hooks.present(ws)
    (out / "hooks_smoke.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1, default=str) + "\n",
                                          encoding="utf-8")
    print(json.dumps({"rc": rep["generate_rc"], "wall_s": rep["wall_s"], "twin": rep.get("twin")},
                     ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
