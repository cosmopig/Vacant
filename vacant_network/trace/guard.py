"""guard — **步驟邊界的不變量**：在每一步結束的那一刻就判定，不等回合結束再回頭翻整份輸出。

這支在架構裡承重什麼：`recorder.post` 在把輸出存進版本庫**之前**叫 `signal()`，用的是這一步
**完整**的輸出；結論（測試綠／紅／讀不出、殼層指令失敗、最後幾行）是一小段結構化欄位，簽進
`step` 事件的 `guard`。回合結束的 `evidence.py` 讀這個欄位，不必再把每一步的原始輸出讀回來重新
解析；`ledger_update()` 把三條不變量的狀態逐步維護在病歷的狀態檔裡，任何時候都是 O(1) 可查。

不變量（每一條在一步結束時就有答案）：

    I1 test_outcome   跑測試的那一步：綠／紅／讀不出——在完整輸出上判定
    I2 open_failure   失敗的殼層指令在同一條（正規化後的）指令再跑成功之前一直「開著」
    I3 stale_green    最後一次綠燈之後又改了程式碼 ⇒ 那次綠燈不再代表現在的程式

**高訊號壓縮**（`compact_output`）：超過 `MAX_OUTPUT_BLOB` 的輸出只存頭＋尾（測試的總結、
錯誤的最後一行都在尾巴），中間換成一行標記，帶完整輸出的 sha256 與位元組數——丟掉的是雜訊，
出處與失敗訊號留著。舊做法只存前 2MB：pytest 的 `1 failed` 總結在第 2MB 之後就整個消失，
回合結束時那一跑變成「讀不出」，「測試都過了」就被放行（`tests/test_trace_guard.py` 重現）。

## 誠實邊界（改碼請保留）

1. 判定用的是 `evidence.py` 原本的同一組正規式（`RUNNERS`、`FAIL_OUT`…），只是換到步驟邊界、
   換成完整輸出——不是新的、更聰明的判準。正規式會錯的地方這裡一樣錯。
2. 沒有 `guard` 欄位的舊病歷照舊走回合結束時重新解析的路（`evidence.py` 兩條路都留著）。
3. 被壓掉的中段不在版本庫裡：追緝要在那一段找值出處就找不到（記成「不知道」，不是「沒有」）。
4. `VACANT_GUARD=0` 關掉步驟邊界判定與頭尾壓縮，回到舊行為——只給量測對照用。
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from typing import Any

from .tools import tool_kind

#: 輸出超過這個大小才壓（和舊的截斷門檻同一個數字：門檻以下逐位元不變）
MAX_OUTPUT_BLOB = 2 * 1024 * 1024
#: 壓縮後保留的頭與尾（字元）
#: 頭留滿舊的 2MB：舊病歷讀得到的值（數字出處檢查靠它），新的一定也讀得到
COMPACT_HEAD = MAX_OUTPUT_BLOB
COMPACT_TAIL = 256 * 1024
TAIL_LINES = 3
LINE_MAX = 240
CODE_EXT = {".py", ".js", ".ts", ".tsx", ".jsx", ".mjs", ".cjs", ".go", ".rs", ".java", ".rb",
            ".php", ".c", ".cc", ".cpp", ".h", ".hpp", ".cs", ".kt", ".swift", ".sh", ".scala"}
_SHELL_FAIL = re.compile(r"Traceback \(most recent call last\)|\bError:|Exception:")


def enabled() -> bool:
    return os.environ.get("VACANT_GUARD", "1") != "0"


def output_bytes(output: Any) -> bytes:
    if isinstance(output, bytes):
        return output
    if isinstance(output, str):
        return output.encode()
    return json.dumps(output, ensure_ascii=False, default=str).encode()


def as_text(data: bytes) -> str:
    from .blame import _as_text
    return _as_text(data.decode("utf-8", "replace"))


def command_of(tool_input: Any) -> str:
    if isinstance(tool_input, dict):
        for k in ("command", "cmd", "script"):
            v = tool_input.get(k)
            if isinstance(v, list):
                v = " ".join(map(str, v))
            if isinstance(v, str) and v.strip():
                return v.strip()
    raw = tool_input if isinstance(tool_input, str) else \
        json.dumps(tool_input, ensure_ascii=False, sort_keys=True, default=str)
    return raw.strip()[:500]


def _tail(text: str) -> list[str]:
    lines = [ln.strip()[:LINE_MAX] for ln in text.strip().splitlines() if ln.strip()]
    return lines[-TAIL_LINES:]


def is_test_run(cmd: str) -> bool:
    from .evidence import RUNNERS, is_test_script_run
    return bool(RUNNERS.search(cmd) or is_test_script_run(cmd))


def test_outcome(text: str, error: str | None) -> str:
    from .evidence import FAIL_OUT, FAIL_OUT_2, PASS_OUT, PASS_OUT_2
    if error or FAIL_OUT.search(text) or FAIL_OUT_2.search(text):
        return "failed"
    if PASS_OUT.search(text) or PASS_OUT_2.search(text):
        return "passed"
    return "unreadable"


def shell_failed(cmd: str, text: str, error: str | None) -> bool:
    from .evidence import _no_match_only
    failed = bool(error) or bool(_SHELL_FAIL.search(text))
    return failed and not _no_match_only(cmd, text + "\n" + str(error or ""))


def signal(tool: str, tool_input: Any, data: bytes | None, error: str | None) -> dict[str, Any] | None:
    """I1／I2 在步驟邊界的判定（完整輸出）。不是殼層指令 ⇒ None。"""
    if tool_kind(tool) != "shell":
        return None
    cmd = command_of(tool_input)
    text = as_text(data) if data is not None else ""
    sig: dict[str, Any] = {"out_bytes": len(data or b"")}
    crashed = shell_failed(cmd, text, error)
    if is_test_run(cmd):
        sig.update(kind="test", outcome=test_outcome(text, error))
    else:
        sig.update(kind="shell", outcome="failed" if crashed else "ok")
    sig["shell_failed"] = crashed
    if sig["kind"] == "test" or sig["outcome"] == "failed":
        sig["tail"] = _tail(text) or ([str(error)[:LINE_MAX]] if error else [])
    return sig


def compact_output(data: bytes) -> bytes:
    """門檻以下原封不動；以上留頭（＝舊的前 2MB）＋尾＋一行出處標記（完整輸出的 sha256 與大小）。"""
    if len(data) <= MAX_OUTPUT_BLOB:
        return data
    if not enabled():
        return data[:MAX_OUTPUT_BLOB]
    text = as_text(data)
    mark = (f"\n…[vacant: {len(data)} bytes of output, middle elided; "
            f"full sha256 {hashlib.sha256(data).hexdigest()}]…\n")
    return (text[:COMPACT_HEAD] + mark + text[-COMPACT_TAIL:]).encode()


#: `compact_output` 插的那一行：出處，不是工具印的內容（讀回來找數字出處時要拿掉）
MARK_RE = re.compile(r"\n…\[vacant: \d+ bytes of output, middle elided; full sha256 [0-9a-f]{64}\]…\n")


def strip_mark(text: str) -> str:
    return MARK_RE.sub("\n", text)


# ── I2／I3：逐步維護的帳 ─────────────────────────────────────────────────
def norm_cmd(cmd: str) -> str:
    from .evidence import _norm_cmd
    return _norm_cmd(cmd)


def _ext(path: str) -> str:
    base = path.rsplit("/", 1)[-1]
    return "." + base.rsplit(".", 1)[-1].lower() if "." in base else ""


def ledger_update(ledger: dict[str, Any], n: int, cmd: str, sig: dict[str, Any] | None,
                  writes: list[dict[str, Any]]) -> list[str]:
    """一步結束時更新帳；回這一步造成的變化（`opened:…`／`closed:…`／`stale`／`green`）。"""
    from .evidence import IMPORT_PROBE, PROBE_CMD
    changes: list[str] = []
    opened = ledger.setdefault("open", {})
    if sig is not None:
        key = norm_cmd(cmd)
        if sig["outcome"] == "failed":
            if sig["kind"] == "test" or not (PROBE_CMD.match(cmd) or IMPORT_PROBE.search(cmd)):
                opened[key] = {"n": n, "kind": sig["kind"], "cmd": cmd[:160],
                               "tail": (sig.get("tail") or [])[-1:]}
                changes.append("opened:" + key)
        elif key in opened and sig["outcome"] in ("ok", "passed"):
            opened.pop(key)
            changes.append("closed:" + key)
        if sig["kind"] == "test":
            ledger["last_test"] = {"n": n, "outcome": sig["outcome"]}
            if sig["outcome"] == "passed":
                ledger["stale"] = None
                changes.append("green")
    # 跑測試那一步自己的寫入（`black app.py && pytest`）發生在測試之前或之中，不算「綠燈之後又改」
    test_step = sig is not None and sig["kind"] == "test"
    code = [str(w.get("path")) for w in writes if _ext(str(w.get("path"))) in CODE_EXT]
    last = ledger.get("last_test") or {}
    if code and not test_step and last.get("outcome") == "passed" and not ledger.get("stale"):
        ledger["stale"] = {"n": n, "path": code[0], "last_pass": last.get("n")}
        changes.append("stale")
    return changes


def violations(ledger: dict[str, Any] | None) -> list[dict[str, Any]]:
    """現在還成立的違反（O(1)：只看帳，不看病歷）。"""
    if not ledger:
        return []
    out = [{"invariant": "open_failure", **v} for v in (ledger.get("open") or {}).values()]
    if ledger.get("stale"):
        out.append({"invariant": "stale_green", **ledger["stale"]})
    last = ledger.get("last_test") or {}
    if last.get("outcome") in ("failed", "unreadable"):
        out.append({"invariant": "test_outcome", **last})
    return out


# ── 高訊號摘要：每一步一行，原始輸出只留出處 ─────────────────────────────
def digest(events: list[dict[str, Any]]) -> dict[str, Any]:
    """病歷 → 給人／給模型讀的精簡版：誰、哪個工具、寫了哪些檔、結論、失敗的最後一行、輸出的 sha256。
    原始輸出、讀到的內容、工作區索引都不帶（它們仍在版本庫，鏈上的 sha256 綁著）。"""
    steps, gaps = [], []
    for e in events:
        t = e.get("type")
        if t == "step":
            a = e.get("actor") or {}
            row: dict[str, Any] = {"n": e.get("n"), "who": f"{a.get('platform')}:"
                                   f"{a.get('agent_type') or 'main'}", "tool": e.get("tool")}
            w = [str(x.get("path")) for x in e.get("writes") or []]
            if w:
                row["writes"] = w[:8]
                if len(w) > 8 or e.get("n_writes"):
                    row["n_writes"] = int(e.get("n_writes") or len(w))
            g = e.get("guard") or {}
            if g:
                row["outcome"] = g.get("outcome")
                if g.get("outcome") in ("failed", "unreadable") and g.get("tail"):
                    row["tail"] = g["tail"][-1]
                if g.get("ledger"):
                    row["ledger"] = g["ledger"]
            if e.get("error"):
                row["error"] = str(e["error"])[:LINE_MAX]
            for k in ("post_missing", "denied", "writes_unknown"):
                if e.get(k):
                    row[k] = True
            if e.get("output_blob"):
                row["out"] = str(e["output_blob"])
            steps.append(row)
        elif t == "unrecorded_change":
            gaps.append({"seq": e.get("seq"), "n": e.get("n"),
                         "paths": [str(c.get("path")) for c in e.get("changes") or []][:8]})
    return {"steps": steps, "gaps": gaps}
