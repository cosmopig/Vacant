"""重複呼叫探針（2026-09-26）：agent 連續兩步跑了同一個指令、拿到同一個輸出之後，一則事實的提示能不能讓它不再跑第三次。

**探索，不是證據**（`decisions/DECISION_20260926_BIGGER_EFFECT_REVIEW.md` §九）。本機正式批次（已經分析完）的 A／C1 組裡，
23／237、21／229 跑有「同一個工具呼叫、同一組參數，連續 3 次以上」——**全部答錯**，幾乎都一路跑到 15 回合上限。
回合預算提醒只在寫明上限時作用；這種「同樣的事再做一次」在一般互動使用裡也會發生。

取正式批次**真的送出過的**請求：最後兩個助理回合各只有一個工具呼叫、兩個呼叫（名稱＋參數）相同、兩個工具結果也相同
——就是 agent 剛把同一件事做了第二次的那一刻。同一通請求：
- **對照**：原樣再送 k 次；
- **提示**：後面接一則 `user` 訊息（pi 把擴充的 custom_message 送成 user 訊息）＝`NOTICE`，送 k 次。
看下一通回覆：再做一次同樣的呼叫（`repeat`）、換一個呼叫（`different`）、不呼叫工具（`text`）；寫了答案檔的話評分。

    python3 ops/eval/local/loop_probe.py --io <代理 io.jsonl> --prefix v3local --arms A C1 --dataset <釘死的題目目錄> \
        --upstream 1003 --draws 2 --max-points 40 --out <輸出 jsonl>

誠實邊界：只看**下一通**；提示的字句是草稿（沒有做成產品）；正式批次的資料已經看過，這一支只回答「值不值得做成候選」。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys
from typing import Any

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from nudge_probe import score, send, written_value  # noqa: E402

NOTICE = ("Vacant: the last two steps made the same {tool} call with the same arguments, and both returned the same "
          "output. Running it again will return the same output.")


def _calls(m: dict[str, Any]) -> list[tuple[str, str]]:
    out = []
    for tc in m.get("tool_calls") or []:
        fn = tc.get("function") or {}
        try:
            args = json.dumps(json.loads(fn.get("arguments") or "{}"), sort_keys=True)
        except ValueError:
            args = str(fn.get("arguments"))
        out.append((str(fn.get("name")), args))
    return out


def _content(m: dict[str, Any]) -> str:
    c = m.get("content")
    if isinstance(c, str):
        return c
    return json.dumps(c, sort_keys=True)


def looped(msgs: list[dict[str, Any]]) -> tuple[str, str] | None:
    """最後兩個助理回合各一個工具呼叫、相同，而且兩個工具結果相同 ⇒ 回那個呼叫；否則 None。"""
    if not msgs or msgs[-1].get("role") != "tool":
        return None
    turns: list[tuple[tuple[str, str], str]] = []
    i = len(msgs) - 1
    while i >= 0 and len(turns) < 2:
        results = []
        while i >= 0 and msgs[i].get("role") == "tool":
            results.append(_content(msgs[i]))
            i -= 1
        if i < 0 or msgs[i].get("role") != "assistant":
            return None
        calls = _calls(msgs[i])
        if len(calls) != 1 or len(results) != 1:
            return None
        turns.append((calls[0], results[0]))
        i -= 1
    if len(turns) == 2 and turns[0] == turns[1]:
        return turns[0][0]
    return None


def reply_kind(resp: dict[str, Any], loop: tuple[str, str]) -> str:
    msg = ((resp.get("choices") or [{}])[0].get("message") or {})
    calls = _calls(msg)
    if not calls:
        return "text"
    return "repeat" if loop in calls else "different"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--io", required=True, type=pathlib.Path)
    ap.add_argument("--prefix", required=True)
    ap.add_argument("--arms", nargs="+", default=["A", "C1"])
    ap.add_argument("--dataset", required=True, type=pathlib.Path)
    ap.add_argument("--proxy", default="http://127.0.0.1:18900")
    ap.add_argument("--upstream", default="1003")
    ap.add_argument("--draws", type=int, default=2)
    ap.add_argument("--max-points", type=int, default=40)
    ap.add_argument("--out", required=True, type=pathlib.Path)
    a = ap.parse_args()
    want = tuple(f"{a.prefix}-g12-off-{arm}-" for arm in a.arms)
    points: dict[str, tuple[dict[str, Any], tuple[str, str]]] = {}
    with a.io.open() as f:
        for ln in f:
            if '"tag": "' + a.prefix not in ln[:400]:
                continue
            d = json.loads(ln)
            tag = d.get("tag", "")
            if not tag.startswith(want) or d.get("status") != 200 or tag in points:
                continue
            body = d.get("request_from_agent") or {}
            loop = looped(body.get("messages") or [])
            if loop:
                points[tag] = (body, loop)
    order = sorted(points, key=lambda t: hashlib.sha256(("loop-probe:" + t).encode()).hexdigest())[: a.max_points]
    print(json.dumps({"pool": len(points), "used": len(order)}), flush=True)
    rows = []
    for tag in order:
        body, loop = points[tag]
        task = tag.split("-")[-2]
        notice = NOTICE.format(tool=loop[0])
        for cond in ("control", "notice"):
            b = body if cond == "control" else dict(body, messages=list(body["messages"]) + [
                {"role": "user", "content": notice}])
            for i in range(a.draws):
                try:
                    resp = send(a.proxy, f"loopprobe-{cond}-{tag}-d{i}", a.upstream, b)
                    kind = reply_kind(resp, loop)
                    wrote, val = written_value(resp)
                    ok = score(a.dataset, task, val) if wrote and val is not None else None
                    err = None
                except Exception as e:  # noqa: BLE001 — 記下來，不猜
                    kind, wrote, val, ok, err = None, False, None, None, f"{type(e).__name__}: {e}"[:300]
                row = {"run": tag, "task": task, "condition": cond, "draw": i, "loop_tool": loop[0],
                       "reply": kind, "wrote": wrote, "value": val, "correct": ok, "error": err,
                       "turn": sum(1 for m in body["messages"] if m.get("role") == "assistant")}
                rows.append(row)
                print(json.dumps(row, ensure_ascii=False), flush=True)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
