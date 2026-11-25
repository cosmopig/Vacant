"""sources — **交件裡每條宣稱來自哪個來源；來源變了，只列出受影響的那幾條**（D2′，2026-11-25）。

這支在架構裡承重什麼：病歷（`recorder.py`）已經記下每一步讀了什麼、寫了什麼，`blame.py` 已經能把
「檔案：行：值」追到「寫下它的那一步 → 值是從哪一步的輸出來的 → 那一步抓了哪個網址」。但兩者都只在
**某條主張不過**時才被叫：沒有一個入口能對一份交件問「每一條各自來自哪裡」，也沒有一個入口能在
**事後**問「那些來源現在還是當時讀到的樣子嗎」。這支補的就是這兩件事，全部重用既有的病歷與追緝：

    claims_in(text)          交件裡的具體值（數字：`evidence.numbers_in` 同一套；版本號 `v1.2.3`）逐行列出
    provenance(ws, path)     每個值 → `blame.blame_location` → 外部來源（網址＋那一步＋當時讀到的內容雜湊）
    check(ws, path)          重讀每個來源（Vacant 自己發 GET，不經模型、0 token），和當時讀到的比：
                             changed／unchanged／unknown／no_source；結果簽進同一條鏈（`source_check` 事件）

「受影響」的判準（寫死）：那一步**當時輸出**的每一個非空行，現在的來源裡都還找得到 ⇒ unchanged；
有任何一行找不到 ⇒ changed。整頁 curl 時等於「agent 看到的那一頁有沒有任何一行變了」；
`curl … | grep …` 時只看 agent 當時真的看到的那幾行。

## 誠實邊界（改碼請保留）

1. **出處是推論層**：`blame` 用值比對往回追，同一個值出現在兩個來源時可能指錯（CLAUDE.md：值比對會被巧合騙）。
   這支不升級它的層級，`provenance` 照抄 `blame` 的 `confidence`／`layer`。
2. 只認 `blame` 判成 `external` 的網址來源（整個指令就是抓網頁、網址不是本機）。這台機器上的伺服器、
   agent 自己算的值、讀工作區的檔 ⇒ `no_source`（呼叫端要自己決定要不要把它們也重查；D2′ 實驗是全部重查）。
3. 重讀用的是 Vacant 這一側的 HTTP GET（照環境變數的代理）。來源對不同客戶端回不同內容、要登入、
   或 agent 當時是用別的參數抓的，比對就可能不準 ⇒ 讀不到一律 `unknown`，不猜 unchanged。
4. 「沒變」只表示 agent 當時看到的那幾行還在，不表示宣稱是對的（它當時就可能抄錯）。
"""
from __future__ import annotations

import hashlib
import pathlib
import re
import urllib.request
from typing import Any, Callable

from . import blame as B
from .evidence import numbers_in
from .locate import Location
from .recorder import Recorder

VERSION_RE = re.compile(r"(?<![\w.])v?\d+(?:\.\d+){2,}(?![\w.])")
UNIT_RE = re.compile(r"\s?([A-Za-z%][A-Za-z%/]*)")
PLACEHOLDER_RE = re.compile(r"_{3,}|\bTODO\b|\bTBD\b")
FETCH_TIMEOUT_S = 20
MAX_BODY = 2 * 1024 * 1024


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()


def claims_in(text: str) -> list[dict[str, Any]]:
    """逐行列出具體值：版本號，以及 `numbers_in` 認得的數字（不在版本號裡面的）。標題行與還沒填的行跳過。"""
    out: list[dict[str, Any]] = []
    for i, line in enumerate(text.splitlines(), start=1):
        s = line.strip()
        if not s or s.startswith("#") or PLACEHOLDER_RE.search(s):
            continue
        spans: list[tuple[int, int]] = []
        for m in VERSION_RE.finditer(line):
            spans.append((m.start(), m.end()))
            out.append({"line": i, "value": m.group(0), "key": m.group(0)})
        for _n, a, b in numbers_in(line):
            if any(a < e and b > st for st, e in spans):
                continue
            # 數字後面緊接的單位字（`30 days`、`100 GB`）一起當比對鍵：同一個數字在別頁當別的量用時
            # （`30 GB`）不會被認成出處。找不到時 `provenance` 退回只用數字。
            m = UNIT_RE.match(line, b)
            key = line[a:m.end()] if m else line[a:b]
            out.append({"line": i, "value": line[a:b], "key": key})
    return out


def provenance(ws: str | pathlib.Path, path: str, *, rec: Recorder | None = None,
               contract: Any = None) -> list[dict[str, Any]]:
    """每個具體值 → 來源。`source` 只在 `blame` 判成外部網址時才有；`seen_sha256` 是那一步當時輸出的雜湊。"""
    ws = pathlib.Path(ws).resolve()
    rec = rec or Recorder(ws)
    trace = B.Trace(rec)
    by_n = {s.n: s for s in trace.steps}
    p = (ws / path)
    text = p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""
    out: list[dict[str, Any]] = []
    for c in claims_in(text):
        b = B.blame_location(trace, Location(path, c["line"], value=c["key"]), contract=contract)
        matched = c["key"]
        if c["key"] != c["value"] and not (b.get("source") or {}).get("ref"):
            b2 = B.blame_location(trace, Location(path, c["line"], value=c["value"]), contract=contract)
            if (b2.get("source") or {}).get("ref"):
                b, matched = b2, c["value"]
        writer = next((x for x in b.get("chain") or [] if str(x.get("via", "")).startswith("wrote ")), None)
        e: dict[str, Any] = {"line": c["line"], "value": c["value"], "matched": matched, "state": b.get("state"),
                             "confidence": b.get("confidence"), "layer": b.get("layer"),
                             "written_by_step": writer.get("step") if writer else None,
                             "source": None}
        src = b.get("source")
        if isinstance(src, dict) and src.get("kind") == "url" and src.get("ref"):
            st = by_n.get(src.get("step"))
            seen = trace.output_text(st) if st is not None else ""
            if st is not None and src.get("into"):
                # 抓回來的內容導進了檔案（`curl U > f`）：agent 看到的是那一步寫出的 f
                seen = trace.file_text(st.post_index, src["into"]) or ""
            e["source"] = {"url": src["ref"], "into": src.get("into"), "step": st.id if st else None,
                           "step_n": src.get("step"),
                           "observed": bool(src.get("observed")),
                           "candidates": src.get("candidates"),
                           "seen_sha256": _sha(seen) if seen else None}
            e["_seen"] = seen
        out.append(e)
    return out


def default_fetch(url: str) -> str:
    """Vacant 自己的 GET（照 `http_proxy`／`https_proxy`）。失敗丟例外，呼叫端記 unknown。"""
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "vacant-source-check"}),
                                timeout=FETCH_TIMEOUT_S) as r:
        return r.read(MAX_BODY).decode("utf-8", "replace")


def _still_there(seen: str, now: str) -> bool:
    lines = [ln.strip() for ln in seen.splitlines() if ln.strip()]
    return bool(lines) and all(ln in now for ln in lines)


def check(ws: str | pathlib.Path, path: str, *, fetch: Callable[[str], str] = default_fetch,
          record: bool = True, contract: Any = None) -> dict[str, Any]:
    """重讀每條宣稱的來源。回 `{"claims": [...], "affected_lines": [...], "counts": {...}}`；
    `record` ⇒ 整份結果（不含讀到的內文，只有雜湊）簽進鏈，事件類型 `source_check`。"""
    ws = pathlib.Path(ws).resolve()
    rec = Recorder(ws)
    rec.checkpoint("source_check")            # 行號要對得上現在的檔（和 `trace blame` 一樣）
    prov = provenance(ws, path, rec=rec, contract=contract)
    cache: dict[str, tuple[str | None, str | None]] = {}
    for e in prov:
        seen = e.pop("_seen", "")
        src = e.get("source")
        if not src:
            e["status"] = "no_source"
            continue
        url = src["url"]
        if url not in cache:
            try:
                body = fetch(url)
                cache[url] = (body, None)
            except Exception as ex:          # noqa: BLE001 — 讀不到＝unknown，不中斷
                cache[url] = (None, f"{type(ex).__name__}: {str(ex)[:160]}")
        body, err = cache[url]
        if body is None:
            e["status"], e["error"] = "unknown", err
            continue
        src["now_sha256"] = _sha(body)
        e["status"] = "unchanged" if seen and _still_there(seen, body) else "changed"
    counts: dict[str, int] = {}
    for e in prov:
        counts[e["status"]] = counts.get(e["status"], 0) + 1
    res = {"path": path, "claims": prov, "counts": counts,
           "affected_lines": sorted({e["line"] for e in prov if e["status"] != "unchanged"}),
           "changed_lines": sorted({e["line"] for e in prov if e["status"] == "changed"})}
    if record:
        rec.append("source_check", {"schema": "vacant-source-check/1", **res})
    return res
