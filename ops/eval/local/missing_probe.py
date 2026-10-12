"""缺檔退回探針（2026-09-27）：agent 說做完、答案檔卻不存在的那一刻，送 Vacant 真的「缺檔退回」那一段，下一個回覆會不會把檔寫出來、寫的對不對。

**機制的量測，不是效果的證據**（`decisions/DECISION_20260926_BIGGER_EFFECT_REVIEW.md` §十二）。效果＝發生率 × 每次救回率；
這一支量後者，而且在介入的那一刻把抽樣雜訊拿掉（同一段對話、只差有沒有退回）。對照條件不用送：沒裝 Vacant 時，那一跑就在這裡結束、沒有檔。

兩組點（都來自本機正式批次，已經分析完、原始紀錄在 repo：`formal/formal_io.jsonl.xz`、`formal_jobs.tar.xz`）：
- **A 組的時刻**：沒裝的那一跑最後一則回覆是「做完了」（沒有工具呼叫）、答案檔不存在。請求＝那一跑最後一通請求的訊息
  ＋那一則最後的回覆（助理）＋ Vacant 真的會送的退回（`review.render` 的 `missing_output`；和正式批次 C1 真的送出的逐字相同）。
- **保真檢查**：C1／C2 真的送過缺檔退回的那幾跑，退回之後的那一通請求原樣再送——拿探針的結果對照真的發生了什麼。

只看**下一個回覆**：有沒有寫 `/app/answer.txt`、寫了什麼、評分器收不收。寫檔之前先算一步的，這裡算「沒寫」（下界）。

    python3 ops/eval/local/missing_probe.py --io <formal_io.jsonl> --rows <stage0 rows.json> --jobs <formal_v3 目錄> \
        --dataset <釘死的 formal 題目目錄> --upstream 1003 --draws 3 --workers 3 --out <輸出 jsonl>
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from nudge_probe import REPO, score, send, written_value  # noqa: E402

sys.path.insert(0, str(REPO))
from vacant_network.trace import review  # noqa: E402

FINDING = {"kind": "missing_output", "path": "answer.txt", "asked": "/app/answer.txt", "finding_id": "probe"}


def final_text(trial: pathlib.Path) -> str:
    last = ""
    for ln in (trial / "agent" / "pi.txt").read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            e = json.loads(ln)
        except ValueError:
            continue
        if e.get("type") == "turn_end":
            m = e.get("message") or {}
            txt = "".join(c.get("text", "") for c in m.get("content") or [] if isinstance(c, dict) and c.get("type") == "text")
            if m.get("stopReason") == "stop":
                last = txt
    return last


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--io", required=True, type=pathlib.Path)
    ap.add_argument("--rows", required=True, type=pathlib.Path)
    ap.add_argument("--jobs", required=True, type=pathlib.Path, help="formal_v3 目錄（還原的 Harbor 目錄）")
    ap.add_argument("--dataset", required=True, type=pathlib.Path)
    ap.add_argument("--proxy", default="http://127.0.0.1:18900")
    ap.add_argument("--upstream", default="1003")
    ap.add_argument("--draws", type=int, default=3)
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--out", required=True, type=pathlib.Path)
    a = ap.parse_args(argv)
    sendback, _ = review.render([FINDING])
    rows = json.loads(a.rows.read_text())
    a_points = {f"v3local-g12-off-A-{r['task']}-s{r['s']}": r for r in rows
                if r["arm"] == "A" and r["final_stop"] == "stop" and r["missing"]}
    fid_points = {f"v3local-g12-off-{r['arm']}-{r['task']}-s{r['s']}": r for r in rows
                  if r["arm"] in ("C1", "C2") and any(x[0] == "continue" and "missing_output" in x[1] for x in r["reviews"])}
    last_req: dict[str, tuple[float, dict[str, Any]]] = {}
    after_sb: dict[str, tuple[float, dict[str, Any]]] = {}
    with a.io.open() as f:
        for ln in f:
            head = ln[:200]
            if '"tag": "v3local-g12-off-' not in head:
                continue
            d = json.loads(ln)
            tag, ts, body = d["tag"], d["ts"], d.get("request_from_agent") or {}
            if d.get("status") != 200:
                continue
            if tag in a_points and (tag not in last_req or ts > last_req[tag][0]):
                last_req[tag] = (ts, body)
            if tag in fid_points:
                msgs = body.get("messages") or []
                if msgs and msgs[-1].get("role") == "user" and "does not exist" in json.dumps(msgs[-1].get("content")) \
                        and (tag not in after_sb or ts < after_sb[tag][0]):
                    after_sb[tag] = (ts, body)                  # 第一次缺檔退回之後的那一通
    jobs: list[tuple[str, str, str, int, dict[str, Any]]] = []
    for tag, r in sorted(a_points.items()):
        if tag not in last_req:
            continue
        trial = next(iter(a.jobs.glob(f"g12-off-A-s{r['s']}/{tag}/dabstep-*__*")), None)
        txt = final_text(trial) if trial else ""
        body = last_req[tag][1]
        msgs = list(body["messages"]) + [{"role": "assistant", "content": txt},
                                         {"role": "user", "content": [{"type": "text", "text": sendback}]}]
        for i in range(a.draws):
            jobs.append((tag, r["task"], "A_sendback", i, dict(body, messages=msgs)))
    for tag, r in sorted(fid_points.items()):
        if tag in after_sb:
            for i in range(a.draws):
                jobs.append((tag, r["task"], "fidelity", i, after_sb[tag][1]))
    print(json.dumps({"A_points": len([t for t in a_points if t in last_req]), "fidelity_points": len(after_sb),
                      "requests": len(jobs)}), flush=True)
    out_rows: list[dict[str, Any]] = []
    lock = threading.Lock()

    def one(job: tuple[str, str, str, int, dict[str, Any]]) -> None:
        tag, task, cond, i, b = job
        try:
            resp = send(a.proxy, f"missprobe-{cond}-{tag}-d{i}", a.upstream, b)
            wrote, val = written_value(resp)
            ok = score(a.dataset, task, val) if wrote and val is not None else None
            err = None
        except Exception as e:  # noqa: BLE001 — 記下來，不猜
            wrote, val, ok, err = False, None, None, f"{type(e).__name__}: {e}"[:300]
        row = {"run": tag, "task": task, "condition": cond, "draw": i, "wrote": wrote, "value": val,
               "correct": ok, "error": err,
               "real_end": ({"reward": fid_points[tag]["reward"], "missing": fid_points[tag]["missing"]}
                            if cond == "fidelity" else None)}
        with lock:
            out_rows.append(row)
            print(json.dumps(row, ensure_ascii=False), flush=True)

    with ThreadPoolExecutor(max(1, a.workers)) as pool:
        list(pool.map(one, jobs))
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in out_rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
