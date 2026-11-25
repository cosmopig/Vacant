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
import html as _html
import pathlib
import re
import urllib.request
from typing import Any, Callable

from . import blame as B
from . import locate as L
from .evidence import numbers_in
from .locate import Location
from .recorder import Recorder

VERSION_RE = re.compile(r"(?<![\w.])v?\d+(?:\.\d+){2,}(?![\w.])")
_DOC_START = re.compile(r"(?i)(?=<!doctype html)")
_HTML_START = re.compile(r"(?i)(?=<html[\s>])")
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


def _segments(text: str) -> set[str]:
    """來源切成文字片段：拿掉標籤（HTML 的每個文字節點各自一段），再按句號切。比整行細——規格表常常整張寫在一行裡。"""
    t = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", text)
    out: set[str] = set()
    for part in re.split(r"<[^>]+>|\n", t):
        part = _html.unescape(part).strip()
        for seg in re.split(r"(?<=[.!?])\s+|[,;]\s+", part):     # 「1,800」裡的逗號後面沒有空白，不會被切開
            seg = " ".join(seg.split())
            if seg:
                out.add(seg)
    return out


def _carriers(text: str, key: str) -> set[str]:
    """來源裡帶著這個值的片段。"""
    return {seg for seg in _segments(text) if L.contains(seg, key)}


_SEG_SPLIT = re.compile(r"\s*(&&|;)\s*")
_STANDALONE_NUM = re.compile(r"(?<![A-Za-z])\d")


def _strip_separators(cmd: str) -> str:
    """拿掉只是分隔用的 `echo`／`printf` 段（`echo ""`、`echo "===p1 done==="`）：參數裡沒有獨立的數字
    （緊跟在字母後面的 `p1` 不算），造不出這支模組要追的數值與版本號。只處理用 `&&`／`;` 串起來的指令；
    `blame` 自己的判準比較嚴（它也追文字值），所以只在這裡放寬。"""
    parts = _SEG_SPLIT.split(cmd.strip())
    segs = parts[0::2]
    keep = [seg for seg in segs
            if not (re.match(r"^(echo|printf)\b", seg) and not _STANDALONE_NUM.search(seg[6:]) and "|" not in seg
                    and ">" not in seg)]
    return " && ".join(keep) if keep else ""


_LOOP = re.compile(r"for\s+(\w+)\s+in\s+([^;]+?)\s*;\s*do\s+(.+?)\s*;?\s*done", re.S)
_SAFE_HEADS = {"echo", "printf", "cat", "ls", "sed", "head", "tail", "grep", "wc", "cd", "true", "sleep", "pwd", "date"}
_CODE_HEADS = re.compile(r"^(?:python|pypy|node|nodejs|ruby|perl|php|bash|sh|zsh|dash|deno|bun|awk|gawk|jq|xargs|eval|source|\.)\b")
_HTML_END = re.compile(r"(?is)</html\s*>")
_LINE_NO = re.compile(r"(?m)^\s*\d+\t")       # Claude Code 的 Read 輸出每行前面的行號


def _expand_loops(cmd: str, known_paths: list[str] | None = None) -> str:
    """`for i in 1 2 3; do curl …/p$i.html; done` ⇒ 依序展開成三段（變數換成值）。只處理單層迴圈；清單是字面值，
    或是對已知檔案的萬用字元（`/tmp/p[1-5].html`，只對這一跑存過的檔展開、照名字排序）。"""
    import fnmatch

    def rep(m: re.Match) -> str:
        var, items, body = m.group(1), m.group(2).split(), m.group(3)
        exp: list[str] = []
        for it in items:
            it = it.strip("\"'")
            if re.search(r"[*?\[]", it):
                hits = sorted(x for x in (known_paths or []) if fnmatch.fnmatch(x, it))
                if not hits:
                    return m.group(0)
                exp += hits
            elif re.search(r"[$`]", it):
                return m.group(0)
            else:
                exp.append(it)
        items = exp
        return " ; ".join(re.sub(r"\$\{?" + var + r"\}?(?!\w)", it, body) for it in items)
    return _LOOP.sub(rep, cmd)


def _segments_of(cmd: str) -> list[str] | None:
    """依 `&&` `;` `||` 與換行切段（不切引號裡的）；看到管線以外的子殼、命令替換就放棄（None）。"""
    out, cur, q = [], [], None
    i = 0
    while i < len(cmd):
        ch = cmd[i]
        if q:
            cur.append(ch)
            if ch == q:
                q = None
        elif ch in "\"'":
            q = ch
            cur.append(ch)
        elif cmd.startswith("&&", i) or cmd.startswith("||", i):
            out.append("".join(cur)); cur = []; i += 2; continue
        elif ch in ";\n":
            out.append("".join(cur)); cur = []
        elif ch == "`" or cmd.startswith("$(", i):
            return None
        else:
            cur.append(ch)
        i += 1
    out.append("".join(cur))
    return [x.strip() for x in out if x.strip()]


def _fetch_plan(cmd: str, cwd: str | None, saved: dict[str, str] | None = None) -> dict[str, Any] | None:
    """一個殼層指令裡的抓網頁動作（第二版，2026-11-25 第二輪）：先展開迴圈、切段；每一段要嘛是只抓網頁
    （`blame` 的判準，可接 head／grep 之類的過濾器），要嘛是造不出 HTML 的動作（echo、cat 檔、ls、cd…）；
    有任何一段跑程式（python、bash -c、awk、jq…）就整步放棄。回 {"stdout_urls": [依序印在輸出裡的網址],
    "files": {絕對或相對路徑: 網址}}。"""
    saved = dict(saved or {})
    segs = _segments_of(_expand_loops(cmd, list(saved)))
    if not segs:
        return None

    def absp(x: str) -> str:
        x = x.strip("\"'")
        return x if x.startswith("/") or not cwd else f"{cwd.rstrip('/')}/{x.lstrip('./')}"
    stdout_urls: list[str] = []
    files: dict[str, str] = {}
    any_fetch = False
    for seg in segs:
        f = B.fetch_of_command(seg)
        if f is not None:
            if f["local"]:
                return None
            any_fetch = True
            outs = f.get("by_output") or {}
            if outs:
                for o, us in outs.items():
                    if len(us) == 1:
                        files[absp(o)] = us[0]
                        saved[absp(o)] = us[0]
            else:
                stdout_urls += f["urls"]
            continue
        head = seg.split()[0] if seg.split() else ""
        if _CODE_HEADS.match(head) or "|" in seg and B.fetch_of_command(seg.split("|")[0]) is None and \
                any(_CODE_HEADS.match(x.strip()) for x in seg.split("|")[1:]):
            return None
        if head == "cd" and len(seg.split()) > 1:
            cwd = seg.split()[1].strip("\"'")
            continue
        if head == "cat" and "|" not in seg and ">" not in seg:
            # 印出這一跑抓下來存好的檔（同一個指令或更早的步驟）＝把那一頁印在輸出裡
            for arg in seg.split()[1:]:
                if not arg.startswith("-") and absp(arg) in saved:
                    stdout_urls.append(saved[absp(arg)])
            continue
        if head not in _SAFE_HEADS:
            return None
    return {"stdout_urls": stdout_urls, "files": files} if (any_fetch or stdout_urls) else None


def _html_docs(txt: str) -> list[str]:
    """輸出裡的 HTML 文件，依序；每份截到 `</html>`（後面 echo、cat 印的東西不算）。"""
    pat = _DOC_START if _DOC_START.search(txt) else _HTML_START
    docs = []
    for c in pat.split(txt):
        if not pat.match(c.lstrip()):
            continue
        m = _HTML_END.search(c)
        docs.append(c[:m.end()] if m else c)
    return docs


def _fetch_records(trace: B.Trace, blamer: B.Blamer) -> list[dict[str, Any]]:
    """病歷裡每一次「抓到某個網址的內容」（第二版）：
      1. 只抓網頁的步驟（`blame` 的判準）：一個網址 ⇒ 整份輸出；
      2. 混合指令（迴圈、echo 分隔、先 cat 自己的檔再抓、cd）：`_fetch_plan` 認得出每一段在做什麼時，
         輸出裡的 HTML 文件依序對上印出來的網址（份數相符才對；推論）；
      3. 導進檔案的（`curl U > f`）：工作區裡的 f ⇒ 那一步寫出的內容；之後任何一步用讀檔工具讀這個 f
         （工作區外也算，例如 /tmp）⇒ 那一次讀到的內容。"""
    out: list[dict[str, Any]] = []
    saved: dict[str, tuple[str, Any]] = {}          # 絕對路徑 → (網址, 抓的那一步)
    ws_root = str(trace.rec.workspace)
    for st in trace.steps:
        inp = trace.input_obj(st)
        tool = str(st.tool).lower()
        if tool in ("read",) and isinstance(inp, dict):
            pth = str(inp.get("path") or inp.get("file_path") or "")
            ap = pth if pth.startswith("/") else (f"{ws_root.rstrip('/')}/{pth}" if ws_root else pth)
            if ap in saved:
                txt = _LINE_NO.sub("", trace.output_text(st) or "")
                if txt.strip():
                    out.append({"seq": st.seq, "n": st.n, "step": st.id, "ctx": st.ctx, "url": saved[ap][0],
                                "into": pth, "text": txt, "via_read": True})
            continue
        cmd = B._command(inp) or ""
        if not cmd:
            continue
        txt = trace.output_text(st) or ""
        cwd = (inp.get("workdir") or inp.get("cwd")) if isinstance(inp, dict) else None
        f = blamer._fetch_of(st)
        if f is not None and not f["local"] and len(f["urls"]) == 1 and not f["outputs"] and txt.strip():
            out.append({"seq": st.seq, "n": st.n, "step": st.id, "ctx": st.ctx, "url": f["urls"][0],
                        "into": None, "text": txt})
            continue
        plan = _fetch_plan(cmd, cwd or ws_root, {k: v[0] for k, v in saved.items()})
        if plan is None:
            continue
        if plan["stdout_urls"] and txt.strip():
            docs = _html_docs(txt)
            if len(docs) == len(plan["stdout_urls"]):
                for u, d in zip(plan["stdout_urls"], docs):
                    out.append({"seq": st.seq, "n": st.n, "step": st.id, "ctx": st.ctx, "url": u,
                                "into": None, "text": d, "split": True})
        for path, u in plan["files"].items():
            ap = path if path.startswith("/") else (f"{ws_root.rstrip('/')}/{path}" if ws_root else path)
            saved[ap] = (u, st)
            rel = blamer._rel(ap) or blamer._rel(path)
            ftxt = trace.file_text(st.post_index, rel) if rel else None
            if ftxt:
                out.append({"seq": st.seq, "n": st.n, "step": st.id, "ctx": st.ctx, "url": u, "into": rel,
                            "text": ftxt})
    return out


def _context_score(line: str, key: str, text: str) -> int:
    """交件那一行的字（產品名、欄名）有幾個也出現在這份來源裡。用來在「好幾個來源都有這個值」時挑一個。"""
    words = {w.lower() for w in re.findall(r"[A-Za-z][A-Za-z]{2,}", line)} - \
        {w.lower() for w in re.findall(r"[A-Za-z]+", key)}
    low = text.lower()
    return sum(1 for w in words if w in low)


def provenance(ws: str | pathlib.Path, path: str, *, rec: Recorder | None = None,
               contract: Any = None) -> list[dict[str, Any]]:
    """每個具體值 → 來源（外部網址）、當時讀到的內容雜湊、之後再讀時仍支持它的最後一次（基準）。

    1. `blame` 找寫下這一行的那一步，以及它的出處。
    2. 同一個工作階段、寫入之前抓過的內容裡含這個值的，都是候選；不只一個網址時，挑和這一行共用字最多的
       （產品名通常只在自己那一頁），平手照 `blame` 的。`ambiguous` 列出其他也含這個值的網址。⇒ 仍是推論層。
    3. 基準：寫入之後 agent 又抓了同一個網址、那一頁仍帶著這個值、而這一行之後沒再改（＝它對著新的來源再確認過）
       ⇒ 基準換成最後那一次；否則用寫入前讀到的那一次。⚠ 新頁面上的值若只剩在別的地方（例如舊版本移進版本紀錄），
       agent 沒改也會被當成確認過——那是 agent 被交辦後沒改對，不會再被重複交辦。
    """
    ws = pathlib.Path(ws).resolve()
    rec = rec or Recorder(ws)
    trace = B.Trace(rec)
    blamer = B.Blamer(trace)
    by_n = {st.n: st for st in trace.steps}
    recs = _fetch_records(trace, blamer)
    p = (ws / path)
    text = p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""
    lines = text.splitlines()
    out: list[dict[str, Any]] = []
    for c in claims_in(text):
        line = lines[c["line"] - 1]
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
        out.append(e)
        w = by_n.get(writer.get("n")) if writer else None
        bsrc = b.get("source") if isinstance(b.get("source"), dict) else {}
        if w is None:
            continue
        cands = []
        for key in dict.fromkeys([matched, c["key"], c["value"]]):
            cands = [r for r in recs if r["seq"] < w.seq and r["ctx"] == w.ctx and L.contains(r["text"], key)]
            if cands:
                matched = key
                break
        if not cands:
            continue
        urls = list(dict.fromkeys(r["url"] for r in cands))
        score = {u: _context_score(line, matched, next(r["text"] for r in reversed(cands) if r["url"] == u))
                 for u in urls}
        best = max(score.values())
        top = [u for u in urls if score[u] == best]
        url = bsrc.get("ref") if bsrc.get("ref") in top else max(top, key=lambda u: max(r["seq"] for r in cands if r["url"] == u))
        origin = max((r for r in cands if r["url"] == url), key=lambda r: r["seq"])
        base = origin
        for r in recs:
            # 寫入之後 agent 又讀了同一頁、那一頁仍帶著這個值，而這一行到現在都沒再改 ⇒ 等於它對著新的來源再確認過
            if r["url"] == url and r["seq"] > max(base["seq"], w.seq) and _carriers(r["text"], matched):
                base = r
        e["matched"] = matched
        e["source"] = {"url": url, "into": origin["into"], "step": origin["step"], "step_n": origin["n"],
                       "observed": origin["into"] is None and not origin.get("split"),
                       "ambiguous": [u for u in urls if u != url] or None,
                       "picked_by": "blame" if url == bsrc.get("ref") else "context",
                       "seen_sha256": _sha(origin["text"]),
                       "baseline_step_n": base["n"], "baseline_sha256": _sha(base["text"])}
        e["_seen"] = base["text"]
    return out


def default_fetch(url: str) -> str:
    """Vacant 自己的 GET（照 `http_proxy`／`https_proxy`）。失敗丟例外，呼叫端記 unknown。"""
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "vacant-source-check"}),
                                timeout=FETCH_TIMEOUT_S) as r:
        return r.read(MAX_BODY).decode("utf-8", "replace")


def _still_there(seen: str, now: str, key: str) -> bool:
    """基準裡帶著這個值的每一個片段，現在的來源裡都還在。基準裡找不到帶值的片段 ⇒ 退回比整份的每一行。"""
    car = _carriers(seen, key)
    if car:
        return car <= _segments(now)
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
        e["status"] = "unchanged" if seen and _still_there(seen, body, e["matched"]) else "changed"
    counts: dict[str, int] = {}
    for e in prov:
        counts[e["status"]] = counts.get(e["status"], 0) + 1
    res = {"path": path, "claims": prov, "counts": counts,
           "affected_lines": sorted({e["line"] for e in prov if e["status"] != "unchanged"}),
           "changed_lines": sorted({e["line"] for e in prov if e["status"] == "changed"})}
    if record:
        rec.append("source_check", {"schema": "vacant-source-check/1", **res})
    return res
