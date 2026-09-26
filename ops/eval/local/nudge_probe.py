"""照不照做探針（零設定 v3，2026-09-26）：gemma-4-12b 收到回合預算提醒之後，會不會把答案寫出來、寫的對不對。

**不是救回率、不是證據**——是評測之前的真模型現實檢查（`decisions/DECISION_20260926_ZERO_CONFIG_V3.md` §五）。
取試跑（沒裝／現版）裡真的送出的請求：第 14 通（＝第 13 回合結束之後、上限 15）送出時答案檔還不存在、第 13 回合有執行工具
（v3 會在這一通後面加提醒的那個時點）。同一通請求：
- **對照**：原樣再送 k 次（模型本來會做什麼）；
- **提醒**：後面接一則 `user` 訊息＝v3 的提醒全文（pi 把擴充的 custom_message 送成 user 訊息），送 k 次。
看回覆有沒有寫 `/app/answer.txt` 的工具呼叫、寫了什麼值、那一題的評分器接不接受。

    python3 ops/eval/local/nudge_probe.py --io <代理 io.jsonl> --prefix pilot2 --dataset <釘死的題目目錄> \
        --proxy http://127.0.0.1:18900 --upstream w401 --draws 3 --out <輸出 jsonl>

誠實邊界：只看**下一通**的回覆，不看之後的回合（模型可能下一通先查、再下一通才寫）；「寫了」是從工具呼叫的文字抽出來的。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import sys
import urllib.request
from collections import defaultdict
from typing import Any

REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "ops" / "eval" / "formal"))

from analyze import score  # type: ignore[import-not-found]  # noqa: E402
from vacant_network.trace.review import render_nudge  # noqa: E402

WRITE_HINT = re.compile(r"answer\.txt")


def requests_by_run(io: pathlib.Path, prefix: str) -> dict[str, list[dict[str, Any]]]:
    runs: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for ln in io.open():
        d = json.loads(ln)
        if d.get("tag", "").startswith(prefix + "-") and d.get("status") == 200:
            runs[d["tag"]].append(d)
    for rs in runs.values():
        rs.sort(key=lambda d: d["ts"])
    return runs


def wrote_answer_before(msgs: list[dict[str, Any]]) -> bool:
    for m in msgs:
        if m.get("role") == "assistant":
            for tc in m.get("tool_calls") or []:
                if WRITE_HINT.search(json.dumps(tc.get("function") or {})):
                    return True
    return False


def written_value(resp: dict[str, Any]) -> tuple[bool, str | None]:
    """回覆裡寫答案檔的工具呼叫 → (有沒有寫, 抽得出來的值)。"""
    msg = ((resp.get("choices") or [{}])[0].get("message") or {})
    for tc in msg.get("tool_calls") or []:
        fn = tc.get("function") or {}
        try:
            args = json.loads(fn.get("arguments") or "{}")
        except ValueError:
            args = {}
        blob = json.dumps(args)
        if not WRITE_HINT.search(blob):
            continue
        if isinstance(args.get("content"), str) and "answer.txt" in str(args.get("path", "")):
            return True, args["content"].strip()
        cmd = str(args.get("command") or "")
        m = re.search(r"(?:echo|printf)\s+(?:-[ne]+\s+)?(['\"]?)(.*?)\1\s*>\s*\S*answer\.txt", cmd, re.S)
        return True, (m.group(2).replace("\\n", "").strip() if m else None)
    return False, None


def send(proxy: str, tag: str, upstream: str, body: dict[str, Any]) -> dict[str, Any]:
    b = dict(body, stream=False)
    b.pop("stream_options", None)
    req = urllib.request.Request(f"{proxy}/t/{tag}/up/{upstream}/think/off/api/v1/chat/completions",
                                 json.dumps(b).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=900) as r:
        return json.load(r)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--io", required=True, type=pathlib.Path)
    ap.add_argument("--prefix", required=True)
    ap.add_argument("--dataset", required=True, type=pathlib.Path)
    ap.add_argument("--proxy", default="http://127.0.0.1:18900")
    ap.add_argument("--upstream", default="w401")
    ap.add_argument("--draws", type=int, default=3)
    ap.add_argument("--budget", type=int, default=15)
    ap.add_argument("--out", required=True, type=pathlib.Path)
    a = ap.parse_args()
    runs = requests_by_run(a.io, a.prefix)
    k = a.budget - 2                     # 第 k 回合結束之後送出的是第 k+1 通
    rows = []
    for tag, rs in sorted(runs.items()):
        if len(rs) < k + 1:
            continue
        body = rs[k]["request_from_agent"]
        msgs = body.get("messages") or []
        if not msgs or msgs[-1].get("role") != "tool" or wrote_answer_before(msgs):
            continue                      # 第 k 回合沒有執行工具、或答案檔已經寫過：v3 不會提醒
        task = tag.rsplit("-s", 1)[0].rsplit("-", 1)[1]
        text, _ = render_nudge(["/app/answer.txt"], turns_left=2, budget=a.budget)
        nudged = dict(body, messages=msgs + [{"role": "user", "content": text}])
        for cond, b in (("control", body), ("reminder", nudged)):
            for i in range(a.draws):
                try:
                    resp = send(a.proxy, f"probe-{cond}-{tag}-d{i}", a.upstream, b)
                    wrote, val = written_value(resp)
                    ok = score(a.dataset, task, val) if wrote and val is not None else None
                    err = None
                except Exception as e:  # noqa: BLE001 — 記下來，不猜
                    wrote, val, ok, err = False, None, None, f"{type(e).__name__}: {e}"[:300]
                row = {"run": tag, "task": task, "condition": cond, "draw": i, "wrote": wrote,
                       "value": val, "correct": ok, "error": err,
                       "request_sha256": hashlib.sha256(json.dumps(b, sort_keys=True).encode()).hexdigest()}
                rows.append(row)
                print(json.dumps(row, ensure_ascii=False), flush=True)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
