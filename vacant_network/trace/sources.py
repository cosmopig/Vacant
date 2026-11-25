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


# ───────────────────────── 第三輪（2026-11-25）：候選集合＋快照、越界守衛、沒重讀就改 ─────────────────────────
#
# 第二輪的確認批次裡，c 漏掉的 28 條：13 條沒有出處（agent 一個指令連抓好幾張 .md／.txt 頁，輸出切不開）、
# 8 條指錯頁（同一個值在好幾頁，單選選錯）、7 條交辦了但 agent 沒重讀就改；另有一次 agent 被交辦 2 行卻把整份報告覆寫。
# 這裡的三個機制都是通用的，彼此用開關分開：
#   candidates  出處＝候選集合：這一跑裡、寫入之前，**任何**指令裡出現網址、而且輸出含這個值的步驟提到的網址都算候選
#               （不必解析指令是不是「只抓網頁」——python urllib、迴圈、混合指令都一樣）；Vacant 交件後自己把候選網址抓一份
#               存成快照（簽進鏈），之後拿「上一次的快照」比「現在」：任一候選頁裡帶著這個值的片段變了 ⇒ 受影響。
#               寧可多交辦，不要漏。值不在任何已知來源裡 ⇒ no_source。
#   guard       越界守衛：agent 改完後，交辦清單以外的行被改或被刪 ⇒ 從改之前的版本還原，記一筆 `source_guard`。只保護
#               沒交辦的行，不替 agent 改答案。只適用逐行的交件（每一行一條宣稱）。
#   reread      沒重讀就改：交辦的行變了，但這一回合裡沒有任何步驟的輸入提到它的候選網址 ⇒ 標出來（呼叫端退回一次）。
#
# 誠實邊界：候選網址是「指令文字裡出現過」——指令裡沒有字面網址（例如網址從檔案讀進來再組出來）就抓不到；
# 快照是 Vacant 這一側的 GET，來源對不同客戶端回不同內容時會不準；守衛用「行首到第一個數字之前的文字」對行，
# 交件不是一行一條時不適用。

_URL_IN_TEXT = re.compile(r"https?://[^\s'\"<>|;()\[\]{},]+")


def _urls_in(text: str) -> list[str]:
    out = []
    for u in _URL_IN_TEXT.findall(text or ""):
        u = u.rstrip(".,:")
        if u not in out and not B._is_local_url(u):
            out.append(u)
    return out


def _snapshots(rec: Recorder) -> dict[str, str]:
    """鏈上最新的來源快照：網址 → 內容的 sha256（內容在內容定址庫）。"""
    snap: dict[str, str] = {}
    for e in rec.events():
        if e.get("type") == "source_snapshot":
            # `Recorder.events()` 把 payload 攤平到最上層；直接讀鏈檔時在 payload 底下——兩種都收
            snap.update(e.get("pages") or (e.get("payload") or {}).get("pages") or {})
    return snap


def _blob_text(rec: Recorder, sha: str | None) -> str | None:
    if not sha:
        return None
    p = rec.blobs.path(sha)
    try:
        return p.read_bytes().decode("utf-8", "replace")
    except OSError:
        return None


def candidates(ws: str | pathlib.Path, path: str, *, rec: Recorder | None = None,
               egress: bool = False, skip_given: bool = False) -> list[dict[str, Any]]:
    """每個具體值 → 候選來源網址（集合）。寫下這一行的那一步之前、同一個工作階段裡，輸入提到網址、輸出含這個值的步驟。
    `egress`（v4）：另外收網路出口紀錄（`source_fetch` 事件）裡、寫下這一行之前實際抓過、內容含這個值的網址——不靠指令文字。"""
    ws = pathlib.Path(ws).resolve()
    rec = rec or Recorder(ws)
    trace = B.Trace(rec)
    blamer = B.Blamer(trace)
    by_n = {st.n: st for st in trace.steps}
    recs = _fetch_records(trace, blamer)
    fetched = egress_records(rec) if egress else []
    ts_of = {int(e["seq"]): int(e.get("ts_ms") or 0) for e in rec.events() if e.get("type") == "step"} if egress else {}
    p = ws / path
    text = p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""
    initial = ""
    if skip_given:                              # v4：agent 動手之前檔裡就有的數字（範本、標籤、實體名裡的數字）不是它的宣稱
        try:
            ent = trace.index(trace.initial).get(path) if trace.initial and trace.initial != "__live__" else None
            initial = rec.blobs.get(ent.sha256).decode("utf-8", "replace") if ent else ""
        except Exception:                       # noqa: BLE001
            initial = ""
    tlines = text.splitlines()
    out: list[dict[str, Any]] = []
    for c in claims_in(text):
        if initial:
            ln_txt = tlines[c["line"] - 1] if 0 < c["line"] <= len(tlines) else ""
            i = ln_txt.find(c["value"])
            if i >= 0 and ln_txt[:i + len(c["value"])].strip() and ln_txt[:i + len(c["value"])] in initial:
                continue
        b = B.blame_location(trace, Location(path, c["line"], value=c["key"]), contract=None)
        writer = next((x for x in b.get("chain") or [] if str(x.get("via", "")).startswith("wrote ")), None)
        w = by_n.get(writer.get("n")) if writer else None
        urls: list[str] = []
        if w is not None:
            for st in trace.steps:
                if st.seq >= w.seq or st.ctx != w.ctx:
                    continue
                us = _urls_in(trace.input_text(st))
                if not us:
                    continue
                o = trace.output_text(st) or ""
                if any(L.contains(o, k) for k in dict.fromkeys([c["key"], c["value"]])):
                    urls += [u for u in us if u not in urls]
            for r in recs:
                if r["seq"] < w.seq and r["ctx"] == w.ctx and r["url"] not in urls and \
                        any(L.contains(r["text"], k) for k in dict.fromkeys([c["key"], c["value"]])):
                    urls.append(r["url"])
        egress_seen: dict[str, str] = {}
        if egress and w is not None:
            t_w = ts_of.get(int(w.seq), 0)
            for f in fetched:                   # 實際抓過的（任何工具）：寫入那一步記下之前抓的、內容含這個值
                if f["ts_ms"] <= t_w and any(L.contains(f["text"], k) for k in dict.fromkeys([c["key"], c["value"]])):
                    if f["url"] not in urls:
                        urls.append(f["url"])
                    egress_seen[f["url"]] = f["text"]
        seen: dict[str, str] = {}
        for r in recs:                          # 每個網址取「含這個值」的最近一筆（同一頁可能被 grep 過好幾次、各取不同欄）
            if r["url"] in urls and any(L.contains(r["text"], k) for k in dict.fromkeys([c["key"], c["value"]])):
                seen[r["url"]] = r["text"]
        for u, t in egress_seen.items():
            seen.setdefault(u, t)
        out.append({"line": c["line"], "value": c["value"], "key": c["key"],
                    "written_by_step": writer.get("step") if writer else None, "candidates": urls, "_seen": seen})
    return out


def snapshot(ws: str | pathlib.Path, path: str, *, fetch: Callable[[str], str] = default_fetch,
             record: bool = True, egress: bool = False) -> dict[str, Any]:
    """把交件裡每條宣稱的候選網址現在的內容抓一份，存進內容定址庫、簽進鏈（`source_snapshot`）。0 token。"""
    ws = pathlib.Path(ws).resolve()
    rec = Recorder(ws)
    rec.checkpoint("source_snapshot")
    if egress:
        ingest_egress(rec)
    urls: list[str] = []
    for e in candidates(ws, path, rec=rec, egress=egress, skip_given=egress):
        urls += [u for u in e["candidates"] if u not in urls]
    pages: dict[str, str] = {}
    errors: dict[str, str] = {}
    for u in urls:
        try:
            pages[u] = rec.blobs.put_bytes(fetch(u).encode("utf-8"))
        except Exception as ex:                 # noqa: BLE001
            errors[u] = f"{type(ex).__name__}: {str(ex)[:120]}"
    res = {"path": path, "pages": pages, "errors": errors}
    if record:
        rec.append("source_snapshot", {"schema": "vacant-source-snapshot/1", **res})
    return res


def check_candidates(ws: str | pathlib.Path, path: str, *, fetch: Callable[[str], str] = default_fetch,
                     record: bool = True, by_value: bool = False, egress: bool = False) -> dict[str, Any]:
    """候選集合版的來源檢查。每條宣稱：拿每個候選網址的「上一次快照」（沒有快照就用 agent 當時讀到的內容）裡帶著這個值的片段，
    和現在的頁面比；任一候選頁的那些片段不在了 ⇒ changed；有候選頁帶著這個值、而且都沒變 ⇒ unchanged；
    沒有任何候選頁帶著這個值 ⇒ no_source；抓不到 ⇒ 當成 changed（寧可多交辦）。檢查完把現在的頁面記成新的快照。"""
    ws = pathlib.Path(ws).resolve()
    rec = Recorder(ws)
    rec.checkpoint("source_check")
    if egress:
        ingest_egress(rec)
    snaps = _snapshots(rec)
    cands = candidates(ws, path, rec=rec, egress=egress, skip_given=by_value or egress)
    now_cache: dict[str, str | None] = {}

    def now(u: str) -> str | None:
        if u not in now_cache:
            try:
                now_cache[u] = fetch(u)
            except Exception:                   # noqa: BLE001
                now_cache[u] = None
        return now_cache[u]

    claims = []
    for e in cands:
        seen = e.pop("_seen")
        per: dict[str, str] = {}
        for u in e["candidates"]:
            prev = _blob_text(rec, snaps.get(u)) or seen.get(u) or ""
            key = e["key"] if _carriers(prev, e["key"]) else e["value"]
            car = _carriers(prev, key)
            if not car:
                continue
            cur = now(u)
            if cur is None:
                per[u] = "unknown"
            elif by_value:
                per[u] = value_status(prev, cur, key) or "changed"
            else:
                per[u] = "unchanged" if car <= _segments(cur) else "changed"
        if not per:
            st = "no_source"
        elif any(v in ("changed", "unknown") for v in per.values()):
            st = "changed"
        else:
            st = "unchanged"
        claims.append({**e, "status": st, "per_url": per})
    pages = {}
    for u, t in now_cache.items():
        if t is not None:
            pages[u] = rec.blobs.put_bytes(t.encode("utf-8"))
    counts: dict[str, int] = {}
    for e in claims:
        counts[e["status"]] = counts.get(e["status"], 0) + 1
    res = {"path": path, "mode": "candidates" + ("+value" if by_value else "") + ("+egress" if egress else ""),
           "claims": claims, "counts": counts,
           "affected_lines": sorted({e["line"] for e in claims if e["status"] != "unchanged"}),
           "changed_lines": sorted({e["line"] for e in claims if e["status"] == "changed"})}
    if record:
        rec.append("source_check", {"schema": "vacant-source-check/1", **res})
        if pages:
            rec.append("source_snapshot", {"schema": "vacant-source-snapshot/1", "path": path, "pages": pages, "errors": {}})
    return res


def _line_key(line: str) -> str:
    m = re.search(r"\d", line)
    return (line[:m.start()] if m else line).strip()


def guard(ws: str | pathlib.Path, path: str, allowed_lines: list[int], before_text: str,
          *, record: bool = True) -> dict[str, Any]:
    """越界守衛：以改之前的版本為底，交辦的行換成 agent 的新版本（用行首到第一個數字之前的文字對行），
    其他行一律維持原樣；有被改或被刪的就寫回檔案並簽一筆 `source_guard`。"""
    ws = pathlib.Path(ws).resolve()
    p = ws / path
    new_text = p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""
    old = before_text.splitlines()
    new_map: dict[str, str] = {}
    for ln in new_text.splitlines():
        new_map.setdefault(_line_key(ln), ln)
    allowed = set(allowed_lines)
    out, restored = [], []
    for i, ln in enumerate(old, start=1):
        if i in allowed:
            out.append(new_map.get(_line_key(ln), ln))
        else:
            out.append(ln)
            if new_map.get(_line_key(ln)) != ln:
                restored.append(i)
    result = "\n".join(out) + ("\n" if before_text.endswith("\n") else "")
    changed = result != new_text
    if changed:
        p.write_text(result, encoding="utf-8")
    res = {"path": path, "allowed": sorted(allowed), "restored_lines": restored, "rewrote_file": changed,
           "before_sha256": _sha(before_text), "agent_sha256": _sha(new_text), "after_sha256": _sha(result)}
    if record and changed:
        rec = Recorder(ws)
        rec.checkpoint("source_guard")          # 還原這次寫檔，在鏈上記成 Vacant 自己的改動
        rec.append("source_guard", {"schema": "vacant-source-guard/1", **res})
    return res


def reread(ws: str | pathlib.Path, path: str, lines: dict[int, list[str]], since_seq: int,
           before_text: str, egress: bool = False) -> dict[str, Any]:
    """沒重讀就改：交辦的行（行號 → 候選網址）在 `since_seq` 之後被改了，但這段時間裡沒有任何步驟的輸入提到它的任一候選網址
    （候選集合空的行，看有沒有任何抓取網址的步驟）⇒ 列進 `not_reread`。"""
    ws = pathlib.Path(ws).resolve()
    rec = Recorder(ws)
    trace = B.Trace(rec)
    after = [st for st in trace.steps if st.seq > since_seq]
    seen_urls: set[str] = set()
    for st in after:
        seen_urls |= set(_urls_in(trace.input_text(st)))
    if egress:                                  # v4：實際抓過的網址（網路出口紀錄）也算重讀
        ingest_egress(rec)
        t0 = next((int(e.get("ts_ms") or 0) for e in rec.events() if int(e.get("seq") or 0) == int(since_seq)), 0)
        seen_urls |= {e["url"] for e in rec.events() if e.get("type") == "source_fetch" and e.get("url")
                      and not e.get("tls") and int(e.get("ts_ms") or 0) >= t0}
    p = ws / path
    cur = (p.read_text(encoding="utf-8", errors="replace") if p.exists() else "").splitlines()
    old = before_text.splitlines()
    cur_map = {_line_key(ln): ln for ln in cur}
    flagged = []
    for ln_no, urls in sorted(lines.items()):
        if ln_no < 1 or ln_no > len(old):
            continue
        before_line = old[ln_no - 1]
        if cur_map.get(_line_key(before_line), before_line) == before_line:
            continue                            # 沒改（或整行不見——那是守衛的事）
        if (urls and not (set(urls) & seen_urls)) or (not urls and not seen_urls):
            flagged.append(ln_no)
    return {"path": path, "since_seq": since_seq, "not_reread": flagged}


# ---------- v4（2026-11-25 第四輪）：受影響看值、抓取紀錄看網路出口 ----------
#
# 第三輪兩個失敗原因的通用修正：
# (1) 「帶著這個值的片段變了」會被每次抓取都變的雜訊（時間戳、計數器、請求 id）騙：同一行有雜訊，片段每次都不同。
#     改成看**值所在的位置還是不是這個值**：JSON 照欄位路徑（陣列元素用「其他欄位相同的最多」對回來，不怕重排）；
#     其他（CSV、表格、md、html、純文字）找「除了這個值之外最像的那一行」，看那一行還有沒有這個值。
#     反面風險：值剛好還在最像的那一行（例如同一行另一欄是同一個值）⇒ 漏判。
# (2) 候選網址只從指令文字找，變數拼出來的網址找不到。改成在 agent 行程的網路出口記錄（`egress.py` 的本機代理寫
#     `<project>/egress.jsonl`，Vacant 讀進鏈成 `source_fetch` 事件），候選＝寫入之前實際抓過、內容含這個值的網址。

import difflib as _difflib
import json as _json

_TOK = re.compile(r"[A-Za-z]+|\d+(?:[.,]\d+)*|[^\sA-Za-z\d]")


def _text_lines(text: str) -> list[str]:
    t = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", text)
    out = []
    for part in re.split(r"<[^>]+>|\n", t):
        part = " ".join(_html.unescape(part).split())
        if part:
            out.append(part)
    return out


def _json_leaves(obj: Any, path: tuple = ()) -> list[tuple[tuple, Any]]:
    if isinstance(obj, dict):
        return [x for k, v in obj.items() for x in _json_leaves(v, path + (k,))]
    if isinstance(obj, list):
        return [x for i, v in enumerate(obj) for x in _json_leaves(v, path + (i,))]
    return [(path, obj)]


def _json_follow(prev: Any, cur: Any, path: tuple) -> tuple[bool, Any]:
    """沿著 prev 的路徑走到 cur 的對應位置；陣列元素用「其餘葉子相同的數量最多」對回來（不怕重排），對不到用同一個索引。"""
    for step in path:
        if isinstance(prev, list) and isinstance(cur, list) and isinstance(step, int):
            el = prev[step] if step < len(prev) else None
            if el is None:
                return False, None
            pl = set((p, _json.dumps(v, sort_keys=True)) for p, v in _json_leaves(el))
            best, bi = -1, None
            for i, ce in enumerate(cur):
                sc = len(pl & set((p, _json.dumps(v, sort_keys=True)) for p, v in _json_leaves(ce)))
                if sc > best:
                    best, bi = sc, i
            if bi is None or best <= 0:
                bi = step if step < len(cur) else None
            if bi is None:
                return False, None
            prev, cur = el, cur[bi]
        elif isinstance(prev, dict) and isinstance(cur, dict) and step in cur:
            prev, cur = prev.get(step), cur[step]
        else:
            return False, None
    return True, cur


def _json_status(prev: Any, cur: Any, key: str) -> str | None:
    hits = [p for p, v in _json_leaves(prev) if v is not None and L.contains(str(v), key)]
    if not hits:
        return None
    for p in hits:
        ok, v = _json_follow(prev, cur, p)
        if not ok or v is None or not L.contains(str(v), key):
            return "changed"
    return "unchanged"


def _line_status(prev: str, cur: str, key: str) -> str | None:
    plines = [x for x in _text_lines(prev) if L.contains(x, key)]
    if not plines:
        return None
    clines = _text_lines(cur)
    ktoks = set(_TOK.findall(key))
    ctoks = [[t for t in _TOK.findall(c) if t not in ktoks] for c in clines]
    for pl in plines:
        a = [t for t in _TOK.findall(pl) if t not in ktoks]
        best, tied = -1.0, []
        for c, b in zip(clines, ctoks):
            r = _difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()
            if r > best + 1e-9:
                best, tied = r, [c]
            elif abs(r - best) <= 1e-9:
                tied.append(c)
        if best < 0.5 or not tied or not all(L.contains(c, key) for c in tied):
            return "changed"
    return "unchanged"


def value_status(prev: str, cur: str, key: str) -> str | None:
    """值所在的位置還是不是這個值。None＝prev 裡沒有這個值（這一頁不是它的來源）。"""
    try:
        pj, cj = _json.loads(prev), _json.loads(cur)
        if isinstance(pj, (dict, list)) and isinstance(cj, (dict, list)):
            return _json_status(pj, cj, key)
    except ValueError:
        pass
    return _line_status(prev, cur, key)


def egress_log_path(rec: Recorder) -> pathlib.Path:
    return rec.dir / "egress.jsonl"


def ingest_egress(rec: Recorder) -> int:
    """把網路出口代理寫下、還沒進鏈的抓取記成 `source_fetch` 事件（網址、狀態、內容 sha256、抓取時間）。回新增筆數。"""
    p = egress_log_path(rec)
    if not p.exists():
        return 0
    have = sum(1 for e in rec.events() if e.get("type") == "source_fetch")
    lines = [ln for ln in p.read_text(encoding="utf-8", errors="replace").splitlines() if ln.strip()]
    n = 0
    for ln in lines[have:]:
        try:
            r = _json.loads(ln)
        except ValueError:
            r = {"bad_line": ln[:200]}
        rec.append("source_fetch", {"schema": "vacant-source-fetch/1", **r})
        n += 1
    return n


def egress_records(rec: Recorder) -> list[dict[str, Any]]:
    out = []
    for e in rec.events():
        if e.get("type") != "source_fetch" or not e.get("url") or e.get("tls"):
            continue
        t = _blob_text(rec, e.get("sha256"))
        if t is None:
            continue
        out.append({"url": e["url"], "ts_ms": int(e.get("ts_ms") or 0), "text": t})
    return out
