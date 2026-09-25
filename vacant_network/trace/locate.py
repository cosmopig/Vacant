"""locate — **錯在繳付物的哪裡**：把一個不過的主張變成「檔案：行：錯的值」。

這支在架構裡承重什麼（`decisions/DECISION_20260924_ACCOUNTABLE_TRACE.md` §4.1、LOOP §二-2）：

收件口的 `ClaimResult` 只說「不過」與一段文字。追緝要從**位置**出發（哪個檔、哪一行、
哪個值），才找得到寫下它的那一步。這支在驗證之後、對**同一份成果**確定性地重新定位——
不改驗證器本身（它們過了 60 條對抗審查，每條有紅燈測試）；`results_digest` 不含證據，
所以簽章與歸檔的裁決都不受影響。

| 驗證器 | 位置 |
|---|---|
| `text` | `must_not_contain` 每個命中的行／欄／字；`must_contain`、標題、字數 ⇒ 檔案層級（缺的東西沒有行） |
| `csv_total` | 報告裡陳述總數的那一行與那個數字；來源＝釘住的 CSV 與重算值 |
| `json_schema` | 錯誤的 JSON 路徑；行號是那個鍵在檔案裡**第一次出現**的行（近似） |
| `citations_resolve` | 對不到來源的引用記號所在的行 |
| `python_checks`／`command` | 輸出裡 `File "<成果內的檔>", line N` 的回溯 |
| 人的標記（`vacant flag`） | 人給的位置 |

## 誠實邊界（改碼請保留）

1. 「缺了什麼」沒有行號（`must_contain` 沒出現）；追緝對這種只能找「最後寫這個檔的人」＝推論層。
2. JSON 路徑 → 行號是文字搜尋的近似；同名鍵多次出現時可能指錯行。
3. 回溯行號只收**成果裡的**檔；錯在檢查腳本自己裡面的，這裡不歸給成果。
4. `allowed` 由呼叫端算出（契約的 include／exclude）；`locate()` 自己不判斷什麼是繳付物，
   給了就照單全收、不給就退回掃 `adir`（呼叫端自己保證範圍時才安全；2026-09-25 對抗審查
   #3、#15、#20、#21）。「不是 UTF-8」只認驗證器 `evidence.problems` 判過的那些，這裡不自己
   讀一次磁碟下這個結論（同一批審查）。
"""
from __future__ import annotations

import dataclasses
import json
import pathlib
import re
from typing import Any

from ..intake import verifiers as V
from ..intake.artifact import glob_to_regex

_NUM_RE = re.compile(r"-?(?:[0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)(?:\.[0-9]+)?")
_TB_RE = re.compile(r'File "([^"]+)", line ([0-9]+)')


@dataclasses.dataclass
class Location:
    path: str
    line: int | None = None          # 1 起算；None ＝ 整個檔（缺的東西）
    col: int | None = None
    value: str | None = None         # 錯的值（逐字）
    kind: str = "offending"          # offending｜missing｜source
    note: str = ""
    #: 這條結論的**身分**用什麼字算（`feedback.finding_id`）；空 ⇒ 退回用 `value` 或 `note`
    #: （多數定位器的 `note` 本來就穩定：正規式、標題名字都是契約寫死的）。只有 `note` 會隨每一輪
    #: 的量測值變的定位器（例如字數規則）才需要另外給一個穩定的 `key`，不然同一條沒解決的主張
    #: 每輪都變成新的 finding id，回饋會錯報「已解決」（2026-09-25 對抗審查 #8、#22）。
    key: str = ""

    def to_json(self) -> dict[str, Any]:
        return {k: v for k, v in dataclasses.asdict(self).items() if v not in (None, "")}

    @classmethod
    def from_json(cls, d: dict[str, Any]) -> "Location":
        return cls(path=str(d["path"]), line=d.get("line"), col=d.get("col"),
                   value=d.get("value"), kind=str(d.get("kind") or "offending"),
                   note=str(d.get("note") or ""), key=str(d.get("key") or ""))


def line_col(text: str, offset: int) -> tuple[int, int]:
    line = text.count("\n", 0, offset) + 1
    col = offset - (text.rfind("\n", 0, offset) + 1) + 1
    return line, col


#: 一個主張最多回幾個位置／一段文字最多數幾次出現（HTTP 收件口遠端就叫得到：不設上限 ⇒ 一份 2 MB 的報告讓
#: 定位花 100 秒；2026-09-25 審查 http#1）
MAX_MATCHES = 50


class _Lines:
    """整段文字的行首位置，查一次 O(log n)（每一個命中都從頭數換行是 O(命中數 × 長度)）。"""

    def __init__(self, text: str):
        import bisect
        self._bisect = bisect.bisect_right
        self._nl = [i for i, ch in enumerate(text) if ch == "\n"]

    def at(self, offset: int) -> tuple[int, int]:
        k = self._bisect(self._nl, offset - 1)
        start = self._nl[k - 1] + 1 if k else 0
        return k + 1, offset - start + 1


def number_of(tok: str) -> float | None:
    return V._number(tok)


def occurrences(text: str, value: str, limit: int = 200) -> list[tuple[int, int, str]]:
    """`value` 在 `text` 裡出現的位置 `(行, 欄, 逐字)`，最多 `limit` 個。數字依數值比對（`3,072`＝`3072`，
    但 `30720` 不含 `3072`——數字要整個 token 相等）；其餘逐字比對（空白正規化）。"""
    out: list[tuple[int, int, str]] = []
    lines: _Lines | None = None
    num = number_of(value.strip()) if value else None
    if num is not None:
        for m in _NUM_RE.finditer(text):
            # 前後不能緊貼數字或小數點（`30720` 裡找不到 `3072`）
            a, b = m.start(), m.end()
            # 數字要是一個獨立的 token：`Q3`、`v2`、`x_10`、`30720` 裡都沒有 `3`／`2`／`10`／`3072`
            if (a > 0 and (text[a - 1].isalnum() or text[a - 1] in "._")) or \
                    (b < len(text) and (text[b].isalnum() or text[b] == "_")):
                continue
            v = number_of(m.group(0))
            if v is not None and v == num:
                lines = lines or _Lines(text)
                ln, c = lines.at(a)
                out.append((ln, c, m.group(0)))
                if len(out) >= limit:
                    break
        return out
    needle = value.strip()
    if len(needle) < 2:
        return out
    start = 0
    while True:
        i = text.find(needle, start)
        if i < 0 or len(out) >= limit:
            break
        lines = lines or _Lines(text)
        ln, c = lines.at(i)
        out.append((ln, c, needle))
        start = i + max(1, len(needle))
    return out


def contains(text: str, value: str) -> bool:
    return bool(occurrences(text, value, limit=1))


def _read(adir: pathlib.Path, rel: str) -> str | None:
    try:
        p = (adir / rel).resolve()
        if adir.resolve() not in (p, *p.parents):
            return None
        return p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _files(adir: pathlib.Path, pattern: str,
          allowed: frozenset[str] | None = None) -> list[str]:
    """`pattern` 在 `adir` 裡的相對路徑。給了 `allowed`（呼叫端算出來的繳付物檔案集合）
    ⇒ 只在那個集合裡比對，**不再掃磁碟**——工作區裡繳付物以外的東西（`node_modules`、
    `.venv`、`__pycache__`、契約排除的路徑）一律看不見，不會擠掉真正的位置
    （2026-09-25 對抗審查 #3、#15、#20、#21：Stop／`vacant do`／`finalize` 這三條路
    給的是活的工作區，不是收件口那份已經套過 include／exclude 的隔離區）。"""
    rx = glob_to_regex(pattern)
    if allowed is not None:
        return sorted(rel for rel in allowed if rx.match(rel))
    out = []
    for p in sorted(adir.rglob("*")):
        if p.is_file():
            rel = p.relative_to(adir).as_posix()
            if rx.match(rel):
                out.append(rel)
    return out


def locate(claim: Any, result: dict[str, Any], adir: str | pathlib.Path, *,
          allowed: frozenset[str] | None = None) -> list[Location]:
    """一個**不過**的主張在成果目錄 `adir` 裡的位置。過的主張回空清單。

    `allowed`：這條主張看得到的繳付物相對路徑集合（例如 `rerun.manifest_of(contract, adir)`
    算出來的那份）。給了 ⇒ 任何要列出「哪些檔」的定位器只在這個集合裡找；不給 ⇒ 退回掃
    `adir`（呼叫端自己已經是 materialize 出來、只含繳付物的目錄時安全，例如收件口）。"""
    if result.get("status") != "FAIL":
        return []
    adir = pathlib.Path(adir)
    params = getattr(claim, "params", {}) or {}
    kind = getattr(claim, "verifier", result.get("verifier"))
    ev = result.get("evidence") or {}
    fn = _LOCATORS.get(str(kind))
    try:
        return fn(params, ev, result, adir, allowed) if fn else []
    except (re.error, ValueError, TypeError, KeyError):
        return []


#: 一個檔案「不是 UTF-8」的位置**只認驗證器自己判過的那些**（§4.1 表格最後一列的延伸；
#: 2026-09-25 對抗審查 #3）：驗證器的 `evidence.problems` 才是它真的看過、真的判定過的檔，
#: 這裡自己再讀一次磁碟（尤其 `allowed` 沒給、退回掃整個工作區時）不可以自己認定「不是 UTF-8」。
_NOT_UTF8_RE = re.compile(r"^(.*): not UTF-8 text$")


def _not_utf8_files(ev: dict[str, Any]) -> set[str]:
    out = set()
    for p in ev.get("problems") or []:
        m = _NOT_UTF8_RE.match(str(p))
        if m:
            out.add(m.group(1))
    return out


def _loc_text(params: dict[str, Any], ev: dict[str, Any], result: dict[str, Any],
              adir: pathlib.Path, allowed: frozenset[str] | None = None) -> list[Location]:
    out: list[Location] = []
    files = _files(adir, str(params.get("path") or ""), allowed)
    if not files:
        return [Location(str(params.get("path")), kind="missing", note="no file matches")]
    not_utf8 = _not_utf8_files(ev)
    for rel in files:
        if rel in not_utf8:
            out.append(Location(rel, kind="missing", note="not UTF-8 text"))
            continue
        txt = _read(adir, rel)
        if txt is None:
            # 讀不到、但驗證器沒把它判成「不是 UTF-8」（例如根本不在它看過的檔裡）：
            # 不可以替它下這個結論
            continue
        lines = _Lines(txt)
        for rx in params.get("must_not_contain") or []:
            for m in re.finditer(rx, txt, re.M):
                ln, c = lines.at(m.start())
                out.append(Location(rel, ln, c, m.group(0), note=f"forbidden {V.show_rx(rx)}"))
                if len(out) >= MAX_MATCHES:
                    return out
        for rx in params.get("must_contain") or []:
            if not re.search(rx, txt, re.M):
                out.append(Location(rel, kind="missing", value=rx,
                                    note=f"does not contain {V.show_rx(rx)}"))
        for h in params.get("required_headings") or []:
            if h.strip().lower() not in V._headings(txt):
                out.append(Location(rel, kind="missing", value=h, note="missing heading"))
    if not out:
        # 字數／大小：整個檔；顯示用驗證器自己的話（不是一律「length rule」），但**身分**要穩
        # （2026-09-25 對抗審查 #8、#22）：字數每一輪都不同，note 逐字塞進 `finding_id` 會讓同一條
        # 沒解決的主張每輪都變成新的 id——回饋錯報「已解決」。身分只認哪幾條長度規則被設了，不認數字。
        why = str(result.get("detail") or "length rule")[:200]
        rule_key = "length:" + ",".join(sorted(
            k for k in ("min_words", "max_words", "max_bytes") if params.get(k) is not None))
        out = [Location(rel, kind="missing", note=why, key=rule_key) for rel in files[:MAX_MATCHES]]
    return out


def _loc_csv_total(params: dict[str, Any], ev: dict[str, Any], result: dict[str, Any],
                   adir: pathlib.Path, allowed: frozenset[str] | None = None) -> list[Location]:
    report = str(params.get("report"))
    txt = _read(adir, report)
    if txt is None:
        return [Location(report, kind="missing", note="report not in the deliverable")]
    pattern = params.get("pattern") or V._DEFAULT_TOTAL_RE
    out = []
    lines = _Lines(txt)
    for m in re.finditer(pattern, txt):
        ln, c = lines.at(m.start(1))
        out.append(Location(report, ln, c, m.group(1),
                            note=f"recomputed {ev.get('recomputed')!r} from {ev.get('source')}"))
        if len(out) >= MAX_MATCHES:
            break
    if not out:
        return [Location(report, kind="missing", value="total", note="no total stated")]
    src = str(params.get("csv") or "")
    if ev.get("recomputed") is not None:
        out.append(Location(src, kind="source", value=_fmt(ev["recomputed"]),
                            note=f"column {params.get('column')!r}, {ev.get('rows')} rows"))
    return out


def _fmt(x: Any) -> str:
    try:
        f = float(x)
        return str(int(f)) if f.is_integer() else repr(f)
    except (TypeError, ValueError):
        return str(x)


def _instance(doc: Any, ptr: str) -> tuple[bool, Any]:
    cur = doc
    for part in [x for x in ptr.split("/") if x]:
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        elif isinstance(cur, list) and part.isdigit() and int(part) < len(cur):
            cur = cur[int(part)]
        else:
            return False, None
    return True, cur


def _loc_json_schema(params: dict[str, Any], ev: dict[str, Any], result: dict[str, Any],
                     adir: pathlib.Path, allowed: frozenset[str] | None = None) -> list[Location]:
    """錯的**值**（那個 JSON 位置上的內容），不是路徑——追緝要追的是誰寫了 -5，不是誰寫了鍵名
    （2026-09-24 審查 blame#3）。缺欄位、根層級的錯 ⇒ 缺的東西。"""
    rel = str(params.get("path"))
    txt = _read(adir, rel)
    if txt is None:
        return [Location(rel, kind="missing", note="not in the deliverable")]
    try:
        doc = json.loads(txt)
    except ValueError:
        return [Location(rel, note=str(result.get("detail"))[:200])]
    out = []
    for msg in ev.get("errors") or []:
        ptr = str(msg).split(":", 1)[0]
        if ptr == "(root)" or "required property" in str(msg):
            out.append(Location(rel, kind="missing", value=ptr, note=str(msg)[:200]))
            continue
        ok, inst = _instance(doc, ptr)
        if not ok or isinstance(inst, (dict, list)):
            out.append(Location(rel, kind="missing", value=ptr, note=str(msg)[:200]))
            continue
        val = inst if isinstance(inst, str) else json.dumps(inst)
        key = ptr.rsplit("/", 1)[-1]
        ln = col = None
        start = txt.find(json.dumps(key)) if not key.isdigit() else 0
        i = txt.find(json.dumps(inst) if not isinstance(inst, str) else json.dumps(inst),
                     max(start, 0))
        if i >= 0:
            ln, col = line_col(txt, i)
        out.append(Location(rel, ln, col, val, note=f"{ptr}: {str(msg)[:180]}"))
    return out or [Location(rel, note=str(result.get("detail"))[:200])]


def _loc_citations(params: dict[str, Any], ev: dict[str, Any], result: dict[str, Any],
                   adir: pathlib.Path, allowed: frozenset[str] | None = None) -> list[Location]:
    rel = str(params.get("path"))
    txt = _read(adir, rel) or ""
    out = []
    for prob in ev.get("problems") or []:
        m = re.match(r"\[([^\]]+)\]", str(prob))
        if not m:
            out.append(Location(rel, kind="missing", note=str(prob)[:200]))
            continue
        cid = m.group(1)
        for rx in (f"[^{cid}]", f"@{cid}"):
            i = txt.find(rx)
            if i >= 0:
                ln, c = line_col(txt, i)
                out.append(Location(rel, ln, c, rx, note=str(prob)[:200]))
                break
        else:
            out.append(Location(rel, value=cid, note=str(prob)[:200]))
    return out


def _loc_traceback(params: dict[str, Any], ev: dict[str, Any], result: dict[str, Any],
                   adir: pathlib.Path, allowed: frozenset[str] | None = None) -> list[Location]:
    out: list[Location] = []
    seen = set()
    root = adir.resolve()

    def inside(cand: pathlib.Path) -> str | None:
        # 只認成果目錄**裡面**的檔：絕對路徑、`..` 一律不碰檔案系統（否則交件的一方能問出主機上哪些檔存在，
        # 驗收者自己的檢查程式與標準庫也會被當成交件的問題；2026-09-25 審查 http#2）
        if cand.is_absolute() or ".." in cand.parts or not cand.parts:
            return None
        q = (root / cand).resolve()
        if root not in q.parents or not q.is_file():
            return None
        return q.relative_to(root).as_posix()

    for m in _TB_RE.finditer(str(result.get("detail") or "")):
        f, ln = m.group(1), int(m.group(2))
        p = pathlib.Path(f)
        rel = inside(p)
        if rel is None:
            # 在拷貝裡跑的：路徑的尾巴對得到成果裡的檔就算（絕對路徑從錨點之後算起）
            parts = p.parts[1:] if p.is_absolute() else p.parts
            for i in range(len(parts)):
                rel = inside(pathlib.Path(*parts[i:]))
                if rel is not None:
                    break
        if rel is None or (rel, ln) in seen:
            continue
        seen.add((rel, ln))
        if len(out) >= MAX_MATCHES:
            break
        txt = _read(adir, rel) or ""
        lines = txt.splitlines()
        val = lines[ln - 1].strip() if 0 < ln <= len(lines) else None
        out.append(Location(rel, ln, value=val, note="traceback"))
    return out


def _loc_exists(params: dict[str, Any], ev: dict[str, Any], result: dict[str, Any],
                adir: pathlib.Path, allowed: frozenset[str] | None = None) -> list[Location]:
    """缺的是**哪一個樣式**（不是隨便列出成果裡的前五個檔；2026-09-25 審查 http#6）——**每一個**
    數量不夠 `min_count` 的樣式都要報，不是只報完全零命中的那些，不然一個「要 3 個、只交 1 個」
    的樣式會整條消失在回饋裡（2026-09-25 對抗審查 #24）。數字優先用驗證器自己 `evidence.counts`
    算過的那份，讓 agent 看到的數字和裁決用的數字是同一份；沒有這份證據（防呆）才自己數。"""
    n_min = int(params.get("min_count") or 1)
    counts_ev = ev.get("counts")
    counts: dict[str, Any] = counts_ev if isinstance(counts_ev, dict) else {}
    out = []
    for pat in params.get("paths") or []:
        p = str(pat)
        n = counts.get(p)
        if not isinstance(n, int):
            n = len(_files(adir, p, allowed))
        if n < n_min:
            out.append(Location(p, kind="missing", note=f"found {n}, need {n_min}"))
    return out


def _loc_forbid(params: dict[str, Any], ev: dict[str, Any], result: dict[str, Any],
                adir: pathlib.Path, allowed: frozenset[str] | None = None) -> list[Location]:
    """哪些檔是驗證器**自己**判定違反的，而不是重新掃一次目錄——`forbid_paths` 驗證器已經在
    繳付物的 manifest 上比對過，`evidence.matched` 就是那份答案；這裡重掃 `adir` 曾經在 Stop／
    `vacant do`／`finalize` 這三條路上把 `node_modules`、`.venv`、契約排除的路徑也掃進來，
    5 個一批的視窗被無關的檔擠滿，真正的違規（例如 `deploy/id_rsa`）反而看不到
    （2026-09-25 對抗審查 #3、#15、#20、#21）。"""
    matched = ev.get("matched")
    if isinstance(matched, list) and matched:
        pats = [str(p) for p in params.get("paths") or []]
        rxs = [(p, glob_to_regex(p)) for p in pats]
        out = []
        for rel in matched:
            rel = str(rel)
            pat = next((p for p, rx in rxs if rx.match(rel)), None)
            note = f"a file the contract forbids ({pat})" if pat else "a file the contract forbids"
            out.append(Location(rel, note=note))
            if len(out) >= MAX_MATCHES:
                break
        return out
    # 防呆：沒有這份證據（例如手接的 result dict）才退回掃描，而且只在 `allowed` 給的集合裡找
    out = []
    for pat in params.get("paths") or []:
        for rel in _files(adir, str(pat), allowed)[:MAX_MATCHES]:
            out.append(Location(rel, note=f"a file the contract forbids ({pat})"))
    return out[:MAX_MATCHES]


_LOCATORS = {"text": _loc_text, "csv_total": _loc_csv_total, "json_schema": _loc_json_schema,
             "citations_resolve": _loc_citations, "python_checks": _loc_traceback,
             "command": _loc_traceback, "exists": _loc_exists, "forbid_paths": _loc_forbid}
