"""twin/smoke_agentrun — **一位合成分身**在真模型上真跑一次：產品路徑從頭到尾，再撤回。

## 這支在架構裡承重什麼

`tests/test_twin_agent_run.py` 用假上游＋fixture agent 證明的是**機制**。這一支是冒煙：
同一條產品路徑（`twinlink generate --engine agent` → `launcher.run` → `twin_agent.sh`
→ pi 0.85.1 → 1003 LM Studio），**跑一格就好**（1003 吞吐 4 串封頂）。

⚠ **特質是合成的**（下面的 `SYNTHETIC_*`），不是任何真人觀眾——所以它的產出可以進版控當證據。
真觀眾的東西**永遠不准**這樣落盤。

它落下的證據（`--out`）：
* `smoke_report.json`：generate 的回報、分身的決定／成品（合成的）、收據驗章結果、
  lifecycle 契約自檢、wire 上的通數與 thinking 判準（`reasoning_content` 在不在）、
  撤回前後 run 目錄的清單與 `erased` 事件；
* `lifecycle.jsonl`：那一跑的事件流（本來就不帶內容，原樣保存）。

用法（在有 pi 的機器上，例如 vacant-dev）：
    PATH=$HOME/.local/opt/node-v22.23.2-linux-x64/bin:$PATH \\
    python3 ops/exhibit/twin/smoke_agentrun.py \\
        --endpoint http://192.168.76.1:1234/v1 --out <證據目錄>
"""
from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import sys
import tempfile
import time

HERE = pathlib.Path(__file__).resolve()
REPO = HERE.parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from ops.exhibit.twin import twinagent, twinlink, twinvault  # noqa: E402
from ops.exhibit.twin.twinstore import KIND_ERASED, KIND_SUBMITTED, TwinStore  # noqa: E402
from vacant_network.vrun import lifecycle  # noqa: E402
from vacant_network.vrun import verify_receipts as vrr  # noqa: E402

SYNTHETIC_ID = "SYN-smoke-20260924"
SYNTHETIC_CARD = {"need": "想把週末的時間安排得不那麼亂", "vibe": "慢熱、念舊、喜歡手寫",
                  "first_line": "我先泡一壺茶再說。"}
SYNTHETIC_TEXT = ("（合成的特質，不是真人）我做事慢，但答應的事一定做完。"
                  "喜歡整理舊照片、會記得朋友的生日，最近覺得週末總是一下就過完了。")


def _listing(root: pathlib.Path) -> list[str]:
    if not root.exists():
        return []
    return sorted(str(p.relative_to(root)) + ("/" if p.is_dir() else "")
                  for p in root.iterdir())


def _wire_stats(wire: pathlib.Path) -> dict:
    """wire 上的事實：幾通、回應裡有沒有 reasoning_content（**thinking 的判準**）。"""
    req = sorted(wire.glob("*.req.bin")) if wire.exists() else []
    resp = sorted(wire.glob("*.resp.bin")) if wire.exists() else []
    rc = 0
    for p in resp:
        b = p.read_bytes()
        if b'"reasoning_content":"' in b and b'"reasoning_content":""' not in b:
            rc += 1
    return {"requests": len(req), "responses": len(resp),
            "responses_with_reasoning_content": rc}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="一位合成分身真跑一次，再撤回")
    ap.add_argument("--endpoint", required=True)
    ap.add_argument("--model", default=twinlink.DEFAULT_MODEL)
    ap.add_argument("--out", required=True)
    ap.add_argument("--timeout", type=float, default=twinagent.DEFAULT_AGENT_TIMEOUT)
    a = ap.parse_args(argv)
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="twin_smoke_"))
    db = tmp / "twinstore.sqlite3"
    events = tmp / "lifecycle.jsonl"
    rep: dict = {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                 "endpoint": a.endpoint, "model": a.model, "synthetic": True}
    try:
        st = TwinStore(db)
        payload, secs = st.vault.seal_card(SYNTHETIC_ID, SYNTHETIC_CARD, SYNTHETIC_TEXT,
                                           ts=int(time.time() * 1000))
        twinvault.append_sealed(st, KIND_SUBMITTED, SYNTHETIC_ID, payload, secs,
                                source="smoke:synthetic", what="card")
        st.close()

        t0 = time.time()
        # 走 **CLI**（產品路徑），不是直接呼叫函式
        import contextlib
        import io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = twinlink.main(["--db", str(db), "generate", "--endpoint", a.endpoint,
                                "--model", a.model, "--engine", "agent",
                                "--parallel", "1", "--agent-timeout", str(a.timeout),
                                "--events", str(events)])
        rep["generate_rc"] = rc
        rep["generate"] = json.loads(buf.getvalue())
        rep["wall_s"] = round(time.time() - t0, 1)

        st = TwinStore(db)
        cur = st.current(SYNTHETIC_ID) or {}
        tw = cur.get("twin") or {}
        rep["twin"] = {k: tw.get(k) for k in (
            "engine", "degrade_kind", "decision", "reason", "artifacts",
            "arrival", "working", "handover", "lines_from", "run_id", "verdict_hash",
            "stop_reason", "accepted", "requests_seen", "count_semantics",
            "agent_rc", "agent_timed_out", "latency_ms", "twin_id")}
        evs = lifecycle.read(events)
        rep["lifecycle"] = {"n": len(evs), "types": [e["type"] for e in evs],
                            "validate_stream": lifecycle.validate_stream(evs)}
        shutil.copyfile(events, out / "lifecycle.jsonl")

        work_root = twinagent.default_work_root(db)
        ws, rd = twinagent.paths_for(work_root, SYNTHETIC_ID)
        rep["receipts"] = [{k: r.get(k) for k in ("verdict", "chain_ok", "mediated",
                                                   "tier", "type_counts", "failures")}
                           for r in vrr.verify_run(rd)]
        rep["wire"] = _wire_stats(rd / "wire_RUN-ON")
        rep["run_dir_before_withdraw"] = _listing(rd)
        rep["workspace_before_withdraw"] = _listing(ws)

        w = twinlink.withdraw(st, SYNTHETIC_ID, reason="smoke:withdraw")
        rep["withdraw"] = {k: w.get(k) for k in (
            "ok", "signed", "fully_erased", "residual_plaintext_seqs",
            "run_artifacts_erased", "run_artifacts_kept_hash_only",
            "run_artifacts_problems", "problems")}
        rep["run_dir_after_withdraw"] = _listing(rd)
        rep["workspace_exists_after_withdraw"] = ws.exists()
        rep["receipts_after_withdraw"] = [r.get("verdict") for r in vrr.verify_run(rd)]
        rep["synthetic_text_left_under_work_root"] = any(
            SYNTHETIC_TEXT.encode("utf-8") in p.read_bytes()
            for p in work_root.rglob("*") if p.is_file())
        rep["erased_event_kind"] = [e["kind"] for e in st.events(
            sub_id=SYNTHETIC_ID, kind=KIND_ERASED)]
        st.close()
    finally:
        (out / "smoke_report.json").write_text(
            json.dumps(rep, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        shutil.rmtree(tmp, ignore_errors=True)
    print(json.dumps({k: rep.get(k) for k in ("generate_rc", "wall_s")}
                     | {"engine": (rep.get("twin") or {}).get("engine"),
                        "decision": (rep.get("twin") or {}).get("decision")},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
