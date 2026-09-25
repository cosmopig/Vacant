"""零設定的證據檢查：agent 說做完的那一刻，只看紀錄，找出「幾乎一定是真的問題」。

這支在架構裡承重什麼：產品原則「裝一次、照常用」的核心（`decisions/DECISION_20260925_ZERO_CONFIG_DESIGN.md`
§二、§五）。沒有契約、不知道正確答案，所以不判對錯；只問**每個決定有沒有根據**：

| 發現 | 條件 |
|---|---|
| `unsourced` 沒有出處的具體值 | 任務有點名資料；值在這一回合新增或改過的行；文件類交付物；值是 agent 自己打出來的；這個任務看過的東西（步驟輸出、讀到的資料、人打的話）裡找不到它——比對時千分位、幣別、四捨五入／截斷、浮點雜訊、科學記號、×100 的百分比、K／M／B、日期的各種寫法都算同一個值；也不是由看過的表格簡單算得出來的；不在豁免裡 |
| `unread` 點名的檔沒打開 | 人打的話裡**單獨**寫了這個檔，這一回合沒有任何一步讀到它 |
| `test_claim` 說測過但紀錄對不上 | 最後的訊息說測試通過／build 成功，但沒跑過、最後一次失敗、或通過之後程式碼又改過 |
| `failed_step` 失敗的步驟被略過 | 跑 agent 自己寫的腳本或讀給定資料的那一步失敗；之後才寫出交付物；後來沒有再成功跑同一件事；最後的訊息也沒提 |

其他（沒讀的資料夾成員、沒點名資料時沒出處的值）只進交件說明（`notes`）。
純函式：只讀病歷，所以可以在任何錄好的病歷上離線重播（量誤報）。

誠實邊界：
1. 「讀到了沒」是**下界**：殼層指令執行中讀了哪些檔看不到，只看指令與腳本的文字裡點名的檔
   （路徑、絕對路徑、檔名，或對資料夾做會讀內容的動作）。所以「沒打開」只在人**單獨點名**的檔上退回。
2. 「找不到出處」＝在**有紀錄的東西**裡找不到；模型從系統提示知道的事（例如今天日期）紀錄裡沒有，
   所以今天與工作階段的日期一律豁免，沒點名資料的任務裡的值只進說明。
3. 比對規則寬（四捨五入、縮寫、簡單推算都算同一個值）：寧可放過編出來但剛好湊得上的值，也不把對的退回。
"""
from __future__ import annotations

import csv
import datetime as _dt
import difflib
import hashlib
import io
import math
import os
import re
from typing import Any

from .blame import Step, Trace
from .recorder import Recorder
from .tools import tool_kind

DOC_EXT = {".md", ".txt", ".rst", ".adoc", ".tex", ".html", ".htm", ".csv", ".tsv", ""}
CODE_HINT_EXT = {".py", ".js", ".ts", ".sh", ".go", ".rs", ".java", ".c", ".cc", ".cpp", ".h",
                 ".rb", ".php", ".cs", ".kt", ".swift", ".json", ".yaml", ".yml", ".toml"}
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", ".pytest_cache", ".mypy_cache",
             "dist", "build", ".cache", "target", ".vacant"}
MAX_DELIVERABLE_BYTES = 2 * 1024 * 1024
MAX_DIR_MATERIALS = 30
MAX_VALUES_PER_FILE = 60
MAX_CORPUS_NUMBERS = 5000

ASSUMPTION_WORDS = re.compile(
    r"\b(assum\w*|estimat\w*|approx\w*|placeholder|tbd|tbc|e\.g\.|for example|example|sample|"
    r"hypothetical|rough|ballpark|forecast\w*|project(ed|ion)|scenario|target\w*|goal|propos\w*|"
    r"plan(ned)? to|aim\w*|objective|kpi)\b|假設|估計|範例|待定|預估|暫定|目標|建議", re.I)
EXEMPT_HEADINGS = re.compile(r"^\s{0,3}#{1,6}\s*(unverified|assumptions?|open questions|tbd|"
                             r"未驗證|假設|待確認)\b", re.I)
READ_VERBS = re.compile(r"\b(python3?|node|awk|grep|rg|cat|head|tail|sed|jq|less|more|read_csv|"
                        r"read_json|open|load|json\.load|pd\.|pandas|csv\.|readFile|fs\.)", re.I)
PROBE_CMD = re.compile(r"^\s*(pip3?|python3? -m pip|uv|npm|pnpm|yarn|npx|apt(-get)?|brew|which|"
                       r"command|type|ls|find|tree|stat|file|wc|du|df|curl|wget|git|echo|pwd|"
                       r"env|printenv|test|\[)\b")
IMPORT_PROBE = re.compile(r"python3?\s+-c\s+['\"]\s*import\s+[\w., ]+['\"]\s*$")
RUNNERS = re.compile(r"\b(pytest|python3? -m (unittest|pytest)|unittest|tox|nox|"
                     r"(npm|pnpm|yarn)( run)? (test|build|lint|typecheck)|jest|vitest|mocha|"
                     r"go test|cargo (test|build|check)|make (test|check|lint)|mvn|gradle|"
                     r"dotnet test|rspec|phpunit|ctest|bazel test)\b")
CLAIMS = re.compile(r"((all )?tests? (now )?(pass|passed|passing|are green|succeed\w*)|test suite "
                    r"(passes|is green)|(build|lint|typecheck)s? (pass\w*|clean|succeed\w*)|"
                    r"tested and (works|passes)|測試(全部)?通過|測試都過)", re.I)
FAIL_OUT = re.compile(r"(FAILED|failures=|errors=|Traceback \(most recent call last\)|\bFAIL\b|"
                      r"\b\d+ failed\b|npm ERR!|error\[E\d+|test result: FAILED|BUILD FAILED|"
                      r"Tests:.*failed|\bError:|Exception:|command not found|No such file)")
PASS_OUT = re.compile(r"(\bOK\b\s*$|\b\d+ passed\b|test result: ok|BUILD SUCCESS|\bPASS\b)", re.M)
MENTIONS_FAILURE = re.compile(r"\b(fail\w*|error\w*|crash\w*|could not|couldn't|did not run|"
                              r"not run|broke|broken)\b|失敗|錯誤", re.I)
ONLY_ANSWER = re.compile(r"\b(only|just) (the )?(final )?answer\b|write only\b|\bONLY\b", re.I)

MONTHS = {m.lower(): i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July", "August", "September",
     "October", "November", "December"], 1)}
MONTHS.update({m[:3].lower(): i for m, i in list(MONTHS.items())})
_MON = "|".join(sorted(MONTHS, key=len, reverse=True))
DATE_RES = [
    (re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b"), "ymd"),
    (re.compile(r"\b(\d{4})/(\d{1,2})/(\d{1,2})\b"), "ymd"),
    (re.compile(r"\b(" + _MON + r")\.? (\d{1,2})(?:st|nd|rd|th)?,? (\d{4})\b", re.I), "mdy"),
    (re.compile(r"\b(\d{1,2}) (" + _MON + r")\.?,? (\d{4})\b", re.I), "dmy"),
    (re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日"), "ymd"),
]
NUM_RE = re.compile(
    r"(?<![\w.#/-])(?P<cur>US\$|NT\$|\$|€|£|¥|USD ?|EUR ?|TWD ?)?"
    r"(?P<num>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)"
    r"(?P<suf>\s?%|\s?(?:[KMB]|bn|mn|million|billion|thousand)\b)?(?![\w.]*\d)", re.I)
VERSION_RE = re.compile(r"\bv?\d+\.\d+\.\d+|\b[vV]\d+(\.\d+)*\b|\bpython ?\d\.\d+", re.I)
TIME_RE = re.compile(r"\b\d{1,2}:\d{2}(:\d{2})?\b")


# ── small helpers ───────────────────────────────────────────────────────

def _ext(path: str) -> str:
    return os.path.splitext(path)[1].lower()


def _skipped(path: str) -> bool:
    return any(part in SKIP_DIRS for part in path.split("/")[:-1])


def _parse_date(m: re.Match, kind: str) -> _dt.date | None:
    try:
        if kind == "ymd":
            return _dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        if kind == "mdy":
            return _dt.date(int(m.group(3)), MONTHS[m.group(1).lower()[:3]], int(m.group(2)))
        return _dt.date(int(m.group(3)), MONTHS[m.group(2).lower()[:3]], int(m.group(1)))
    except (ValueError, KeyError):
        return None


def dates_in(text: str) -> list[tuple[str, _dt.date, int, int]]:
    out = []
    for rx, kind in DATE_RES:
        for m in rx.finditer(text):
            d = _parse_date(m, kind)
            if d is not None:
                out.append((m.group(0), d, m.start(), m.end()))
    return out


class Num:
    """寫出來的一個數：值、小數位數、是不是百分比、縮寫的倍數。"""

    def __init__(self, raw: str, value: float, decimals: int, pct: bool, scale: float):
        self.raw, self.value, self.decimals, self.pct, self.scale = raw, value, decimals, pct, scale

    def candidates(self) -> list[tuple[float, float]]:
        """(要比對的值, 容許差)：四捨五入到寫出的位數、截斷、百分比與縮寫都換算回原單位。"""
        tol = 0.5 * 10 ** (-self.decimals) + 1e-9
        out = [(self.value * self.scale, tol * self.scale)]
        if self.pct:
            out.append((self.value / 100.0, tol / 100.0))
        return out


def numbers_in(text: str) -> list[tuple[Num, int, int]]:
    out = []
    bad = [(m.start(), m.end()) for m in VERSION_RE.finditer(text)] + \
          [(m.start(), m.end()) for m in TIME_RE.finditer(text)] + \
          [(s, e) for _, _, s, e in dates_in(text)]
    for m in NUM_RE.finditer(text):
        if any(s <= m.start() < e for s, e in bad):
            continue
        raw_num = m.group("num")
        try:
            v = float(raw_num.replace(",", ""))
        except ValueError:
            continue
        dec = len(raw_num.split(".")[1]) if "." in raw_num and "e" not in raw_num.lower() else 0
        suf = (m.group("suf") or "").strip().lower()
        pct = suf == "%"
        scale = {"k": 1e3, "thousand": 1e3, "m": 1e6, "mn": 1e6, "million": 1e6, "b": 1e9,
                 "bn": 1e9, "billion": 1e9}.get(suf, 1.0)
        out.append((Num(m.group(0).strip(), v, dec, pct, scale), m.start(), m.end()))
    return out


def _significant(n: Num) -> bool:
    """值得查的數：有幣別／百分比／縮寫，或至少兩位有效數字；不查 0–10 的整數、單獨的年份。"""
    affix = n.pct or n.scale != 1.0 or bool(re.match(r"\D", n.raw))
    if affix:
        return True
    if n.decimals == 0 and float(n.value).is_integer():
        iv = int(n.value)
        if 0 <= iv <= 10 or 1900 <= iv <= 2100:
            return False
    digits = re.sub(r"\D", "", n.raw.split("e")[0].split("E")[0]).lstrip("0")
    return len(digits) >= 2


# ── the pass ────────────────────────────────────────────────────────────

class Evidence:
    def __init__(self, rec: Recorder, *, platform: str, session: str,
                 final_text: str | None = None, today: _dt.date | None = None):
        self.rec = rec
        self.tr = Trace(rec)
        self.platform, self.session = platform, session
        self.final_text = final_text or ""
        self.today = today or _dt.date.today()
        self.notes: dict[str, Any] = {}

    # window ──────────────────────────────────────────────────────────
    def _mine(self, actor: dict[str, Any]) -> bool:
        return str(actor.get("platform")) == self.platform and \
            str(actor.get("session")) == self.session

    def window(self) -> tuple[int, list[str], list[Step]]:
        """回 (起點 seq, 人的要求原文, 這一回合的步驟)。起點＝這個工作階段最後一則人打的要求
        （含 `vacant do` 交給這一跑的任務）；沒有就從這個工作階段的第一步開始。"""
        start, texts = -1, []
        do_runs = {run for run, sess in self.tr.do_sessions.items()
                   if f"{self.platform}:{self.session}" in sess}
        for p in self.tr.prompts:
            src = str(p.get("source") or "user")
            ps = str(p.get("session") or "")
            person = (src == "user" and ps == self.session) or \
                     (src == "vacant do" and (ps in ("*",) or ps.removeprefix("do:") in do_runs))
            if person:
                start = int(p["seq"])
                texts = [self.tr.prompt_text(p)]
        steps = [s for s in self.tr.steps if s.seq > start and self._mine(s.actor)]
        if start < 0:
            self.notes["window_basis"] = "session_start"
        return start, texts, steps

    # deliverables and changed lines ─────────────────────────────────
    def deliverables(self, steps: list[Step]) -> tuple[dict[str, tuple[str, str]], str | None]:
        """路徑 → (這一回合開始時的內容, 現在的內容)。只收這一回合的步驟寫過、現在還在的文字檔。"""
        latest = self.tr.latest_index()
        start_idx = steps[0].pre_index if steps and steps[0].pre_index else self.tr.initial
        written: dict[str, Step] = {}
        for s in steps:
            for w in s.writes:
                written[str(w["path"])] = s
        out = {}
        idx = self.tr.index(latest)
        for path in written:
            e = idx.get(path)
            if e is None or _skipped(path) or getattr(e, "size", 0) > MAX_DELIVERABLE_BYTES:
                continue
            now = self.tr.file_text(latest, path)
            if now is None or "\x00" in now:
                continue
            out[path] = (self.tr.file_text(start_idx, path) or "", now)
        return out, start_idx

    # materials ───────────────────────────────────────────────────────
    def materials(self, prompt_texts: list[str], start_idx: str | None
                  ) -> tuple[list[str], list[str]]:
        """人打的話裡點名的資料：(單獨點名的檔, 點名的資料夾裡的檔)。只認路徑形式：
        有副檔名的檔名、含 `/` 的路徑、或用反引號／引號包起來的資料夾名。"""
        files = sorted(self.tr.index(start_idx))
        root = str(self.rec.workspace)
        named, in_dirs = [], []
        for text in prompt_texts:
            for tok in re.findall(r"`[^`]+`|\"[^\"]+\"|'[^']+'|\S+", text):
                quoted = tok[:1] in "`\"'"
                t = tok.strip("`\"'()[]<>{}").rstrip(".,;:!?")
                if not t or " " in t.strip():
                    continue
                if t.startswith(root + "/"):
                    t = t[len(root) + 1:]
                elif t.startswith("/"):
                    t = t.lstrip("/")
                t = t.removeprefix("./")
                if re.search(r"\.[A-Za-z0-9]{1,6}$", t) and not t.endswith("/"):
                    hits = [f for f in files if f == t or f.endswith("/" + t)]
                    if not hits and "/" not in t:
                        hits = [f for f in files if f.rsplit("/", 1)[-1] == t]
                    if len(hits) == 1:
                        named.append(hits[0])
                    continue
                d = t.rstrip("/")
                if not d or not ("/" in t or quoted):
                    continue
                parts = d.split("/")                  # 專案根以外的絕對路徑：逐層去掉前面再比
                for k in range(len(parts)):
                    cand = "/".join(parts[k:])
                    if any(f.startswith(cand + "/") for f in files):
                        d = cand
                        break
                under = [f for f in files if f.startswith(d + "/")]
                if under and len(under) <= MAX_DIR_MATERIALS:
                    in_dirs.extend(under)
        named = sorted(dict.fromkeys(named))
        return named, sorted(set(in_dirs) - set(named))

    def observed(self, steps: list[Step], candidates: list[str], deliverables: set[str]) -> set[str]:
        root = str(self.rec.workspace)
        seen: set[str] = set()
        scripts: dict[str, str] = {}            # 這一回合寫的腳本 → 內容
        for s in steps:
            for w in s.writes:
                p = str(w["path"])
                if _ext(p) in {".py", ".js", ".ts", ".sh", ".mjs", ".r", ".jl"}:
                    scripts[p] = self.tr.file_text(s.post_index, p) or ""
        texts = []
        for s in steps:
            kind = tool_kind(s.tool)
            t = self.tr.input_text(s)
            if kind in ("read", "search", "shell", "fetch", "agent", "other"):
                texts.append(t)
            if kind == "shell":
                for sp, body in scripts.items():
                    if re.search(r"(?<![\w.-])" + re.escape(sp.rsplit("/", 1)[-1]) + r"\b", t):
                        texts.append(body)
        for f in candidates:
            base = f.rsplit("/", 1)[-1]
            d = f.rsplit("/", 1)[0] if "/" in f else ""
            pats = [re.escape(root + "/" + f), r"(?<![\w.-])" + re.escape(f),
                    r"(?:^|[\s\"'`/{(+=,:])" + re.escape(base) + r"(?![\w-])"]
            for t in texts:
                if any(re.search(p, t) for p in pats):
                    seen.add(f)
                    break
                # 對整個資料夾做會讀內容的動作（`grep -r x data`、`cat data/*`、`os.listdir('data')`）：
                # 資料夾名後面不接檔名才算——`head data/payments.csv` 只讀了那一個檔
                if d and READ_VERBS.search(t) and re.search(
                        r"(?<![\w.-])" + re.escape(d) + r"/?(\*[^\s\"'`]*)?(?=[\s\"'`),;\]]|$)", t):
                    seen.add(f)
                    break
        return seen

    # the corpus of what this task observed ─────────────────────────
    def corpus(self, steps: list[Step], deliverables: set[str], observed_files: set[str],
               start_idx: str | None, prompt_texts: list[str]) -> str:
        parts = list(prompt_texts)
        for s in steps:
            kind = tool_kind(s.tool)
            if kind == "write":
                continue
            out = self.tr.output_text(s)
            if not out:
                continue
            inp = self.tr.input_text(s)
            refs = set(re.findall(r"[\w./-]+\.[A-Za-z0-9]{1,6}", inp))
            if refs and all(any(r.endswith(d) or d.endswith(r) for d in deliverables)
                            for r in refs):
                continue                          # 只是回頭讀自己寫的交付物：不算出處
            parts.append(out)
        for f in observed_files:
            t = self.tr.file_text(start_idx, f)
            if t:
                parts.append(t[:2_000_000])
        return "\n".join(parts)

    # derived numbers from observed tables ───────────────────────────
    def derived(self, corpus_tables: list[str]) -> list[float]:
        out: list[float] = []
        for text in corpus_tables:
            try:
                rows = list(csv.reader(io.StringIO(text)))
            except csv.Error:
                continue
            if len(rows) < 2 or len(rows[0]) < 2 or len(rows) > 200_000:
                continue
            head, body = rows[0], rows[1:]
            cols = list(zip(*[r for r in body if len(r) == len(head)]))
            numeric: dict[int, list[float]] = {}
            for i, col in enumerate(cols):
                vals = []
                for v in col:
                    try:
                        vals.append(float(v.replace(",", "").replace("$", "").strip()))
                    except ValueError:
                        break
                else:
                    if vals:
                        numeric[i] = vals
            for vals in numeric.values():
                out += [sum(vals), sum(vals) / len(vals), float(len(vals)), min(vals), max(vals)]
            for gi, gcol in enumerate(cols):
                if gi in numeric:
                    continue
                keys: dict[str, list[int]] = {}
                for r_i, g in enumerate(gcol):
                    key_forms = {g}
                    for _, d, _, _ in dates_in(g):
                        key_forms |= {f"y{d.year}", f"m{d.year}-{d.month}",
                                      f"q{d.year}-{(d.month - 1) // 3}"}
                    for k in key_forms:
                        keys.setdefault(k, []).append(r_i)
                if len(keys) > 500:
                    continue
                for vi, vals in numeric.items():
                    for idxs in keys.values():
                        out.append(sum(vals[i] for i in idxs if i < len(vals)))
            if len(out) > MAX_CORPUS_NUMBERS:
                break
        return out[:MAX_CORPUS_NUMBERS]

    # the checks ──────────────────────────────────────────────────────
    def run(self) -> dict[str, Any]:
        start, prompt_texts, steps = self.window()
        delivs, start_idx = self.deliverables(steps)
        named, dir_members = self.materials(prompt_texts, start_idx)
        deliv_set = set(delivs)
        observed = self.observed(steps, named + dir_members, deliv_set)
        findings: list[dict[str, Any]] = []
        unread_named = [f for f in named if f not in observed and f not in deliv_set]
        unread_dir = [f for f in dir_members if f not in observed and f not in deliv_set]
        for f in unread_named:
            findings.append({"kind": "unread", "path": f})
        materials_named = bool(named or dir_members)
        corpus = self.corpus(steps, deliv_set, observed, start_idx, prompt_texts)
        values, value_notes = self._values(steps, delivs, corpus, prompt_texts, materials_named)
        only_answer = any(ONLY_ANSWER.search(t) for t in prompt_texts)
        for v in values:
            v["single_answer"] = only_answer or v.pop("_short")
            if unread_dir or unread_named:
                v["unread_attach"] = (unread_named + unread_dir)[:6]
            findings.append(v)
        findings += self._test_claim(steps, delivs)
        findings += self._failed_steps(steps, delivs, named + dir_members)
        scope = self.rec.dir.name
        for fd in findings:
            fd["finding_id"] = finding_id(fd, scope)
        return {"window_start": start, "steps": len(steps), "deliverables": sorted(delivs),
                "materials_named": named, "materials_in_dirs": dir_members,
                "observed": sorted(observed), "unread_dir": unread_dir,
                "values": value_notes, "findings": findings, "notes": self.notes,
                "final_text_seen": bool(self.final_text)}

    def _values(self, steps: list[Step], delivs: dict[str, tuple[str, str]], corpus: str,
                prompt_texts: list[str], materials_named: bool
                ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        notes: dict[str, Any] = {"checked": 0, "traced": 0, "derived": 0, "exempt": 0,
                                 "not_typed": 0, "not_traced_note_only": []}
        corpus_nums = [n.value * n.scale for n, _, _ in numbers_in(corpus)][:MAX_CORPUS_NUMBERS]
        corpus_nums += [n.value for n, _, _ in numbers_in(corpus) if n.pct][:500]
        tables = [corpus]
        for s in steps:
            tables.append(self.tr.output_text(s))
        derived = self.derived(tables)
        pool = corpus_nums + derived
        pool_small = pool[:300]
        pairs = []
        for i, a in enumerate(pool_small):
            for b in pool_small[i + 1:]:
                pairs += [a + b, abs(a - b)]
                if b:
                    pairs += [a / b, 100 * a / b]
                if a:
                    pairs += [b / a, 100 * b / a]
        corpus_dates = {d for _, d, _, _ in dates_in(corpus)}
        prompt = "\n".join(prompt_texts)
        prompt_dates = {d for _, d, _, _ in dates_in(prompt)}
        prompt_nums = [n for n, _, _ in numbers_in(prompt)]
        today = {self.today, self.today - _dt.timedelta(days=1)}
        step_inputs = [(s, self.tr.input_text(s)) for s in steps]
        out = []
        for path, (old, new) in sorted(delivs.items()):
            ext = _ext(path)
            if ext in CODE_HINT_EXT or ext not in DOC_EXT:
                continue
            lines = new.splitlines()
            changed = _changed_lines(old, new)
            exempt_block = _exempt_lines(lines)
            nonempty = [ln for ln in lines if ln.strip()]
            short = len(nonempty) <= 2
            count = 0
            for ln_no in changed:
                line = lines[ln_no - 1]
                if ln_no in exempt_block:
                    continue
                labelled = (not short) and ASSUMPTION_WORDS.search(line)
                items: list[tuple[str, Any]] = []
                for raw, d, _, _ in dates_in(line):
                    items.append((raw, d))
                for n, s_, e_ in numbers_in(_strip_code(line)):
                    if _significant(n):
                        items.append((n.raw, n))
                for raw, obj in items:
                    count += 1
                    if count > MAX_VALUES_PER_FILE:
                        break
                    notes["checked"] += 1
                    if labelled:
                        notes["exempt"] += 1
                        continue
                    if isinstance(obj, _dt.date):
                        if obj in today or obj in prompt_dates:
                            notes["exempt"] += 1
                            continue
                        if obj in corpus_dates:
                            notes["traced"] += 1
                            continue
                    else:
                        if any(_num_match(obj, p.value * p.scale) for p in prompt_nums):
                            notes["exempt"] += 1
                            continue
                        if any(_num_match(obj, c) for c in corpus_nums):
                            notes["traced"] += 1
                            continue
                        if any(_num_match(obj, c) for c in derived) or \
                                any(_num_match(obj, c) for c in pairs):
                            notes["derived"] += 1
                            continue
                    if not _typed(raw, obj, path, step_inputs):
                        notes["not_typed"] += 1       # 由它跑的程式算出來寫進去的：算在這個任務裡
                        continue
                    if not materials_named:
                        notes["not_traced_note_only"].append(f"{path} line {ln_no} {raw}")
                        continue
                    out.append({"kind": "unsourced", "path": path, "line": ln_no, "value": raw,
                                "_short": short})
        return out, notes

    def _test_claim(self, steps: list[Step], delivs: dict[str, tuple[str, str]]
                    ) -> list[dict[str, Any]]:
        m = CLAIMS.search(self.final_text or "")
        if not m:
            return []
        quote = _sentence_around(self.final_text, m.start(), m.end())
        runs = []
        for s in steps:
            if tool_kind(s.tool) != "shell":
                continue
            cmd = _command_of(self.tr, s)
            if not RUNNERS.search(cmd):
                continue
            out = self.tr.output_text(s)
            if s.error or FAIL_OUT.search(out):
                runs.append((s, "failed", cmd))
            elif PASS_OUT.search(out):
                runs.append((s, "passed", cmd))
            else:
                runs.append((s, "unreadable", cmd))
        if not runs:
            return [{"kind": "test_claim", "sub": "none", "quote": quote}]
        last, outcome, cmd = runs[-1]
        if outcome == "failed":
            return [{"kind": "test_claim", "sub": "failed", "quote": quote, "step": last.n,
                     "cmd": cmd}]
        if outcome == "unreadable":
            self.notes["test_outcome_unreadable"] = last.n
            return []
        code_changes = [s for s in steps if s.seq > last.seq and any(
            _ext(str(w["path"])) in CODE_HINT_EXT - {".json", ".yaml", ".yml", ".toml"}
            for w in s.writes)]
        if code_changes:
            s = code_changes[-1]
            p = next(str(w["path"]) for w in s.writes
                     if _ext(str(w["path"])) in CODE_HINT_EXT)
            return [{"kind": "test_claim", "sub": "stale", "quote": quote, "step": s.n,
                     "last_pass": last.n, "path": p}]
        return []

    def _failed_steps(self, steps: list[Step], delivs: dict[str, tuple[str, str]],
                      materials: list[str]) -> list[dict[str, Any]]:
        out = []
        written_scripts = {str(w["path"]).rsplit("/", 1)[-1] for s in steps for w in s.writes
                           if _ext(str(w["path"])) in {".py", ".js", ".ts", ".sh", ".mjs"}}
        for i, s in enumerate(steps):
            if tool_kind(s.tool) != "shell":
                continue
            cmd = _command_of(self.tr, s)
            outp = self.tr.output_text(s)
            failed = bool(s.error) or bool(re.search(r"Traceback \(most recent call last\)|"
                                                     r"\bError:|Exception:", outp))
            if not failed or PROBE_CMD.match(cmd) or IMPORT_PROBE.search(cmd) or \
                    RUNNERS.search(cmd):
                continue
            runs_own = any(re.search(r"(?<![\w.-])" + re.escape(b) + r"\b", cmd)
                           for b in written_scripts)
            reads_given = any(m in cmd or m.rsplit("/", 1)[-1] in cmd for m in materials)
            if not (runs_own or reads_given):
                continue
            later = steps[i + 1:]
            if not any(w for t in later for w in t.writes if str(w["path"]) in delivs):
                continue
            norm = _norm_cmd(cmd)
            if any(tool_kind(t.tool) == "shell" and _norm_cmd(_command_of(self.tr, t)) == norm
                   and not t.error and not re.search(r"Traceback|\bError:",
                                                     self.tr.output_text(t)) for t in later):
                continue
            if self.final_text and MENTIONS_FAILURE.search(self.final_text):
                continue
            err = next((ln for ln in reversed(outp.strip().splitlines()) if ln.strip()),
                       str(s.error or "failed"))
            out.append({"kind": "failed_step", "step": s.n, "cmd": cmd, "error": err})
        return out


# ── module-level helpers ────────────────────────────────────────────────

def finding_id(f: dict[str, Any], scope: str) -> str:
    key = {"unsourced": (f.get("path"), f.get("value")), "unread": (f.get("path"),),
           "test_claim": (f.get("sub"),), "failed_step": (_norm_cmd(f.get("cmd") or ""),)}
    raw = repr((scope, f["kind"], key.get(f["kind"], ())))
    return "z_" + hashlib.sha256(raw.encode()).hexdigest()[:10]


def _num_match(n: Num, observed: float) -> bool:
    if observed is None or (isinstance(observed, float) and math.isnan(observed)):
        return False
    for target, tol in n.candidates():
        if abs(observed - target) <= tol:
            return True
        # 截斷：寫出的位數以下直接捨去
        if target >= 0 and 0 <= observed - target < 2 * tol:
            return True
    return False


def _typed(raw: str, obj: Any, path: str, step_inputs: list[tuple[Step, str]]) -> bool:
    """這個值是 agent 自己打出來的：寫這個交付物的步驟的輸入（寫檔工具的內容、殼層的 echo／heredoc、
    內嵌程式碼裡的字面值）裡就有它。由程式算出來寫進去的（輸入裡沒有這個字面值）不算。"""
    forms = {raw, raw.replace(",", "")}
    if isinstance(obj, Num):
        forms.add(re.sub(r"[^\d.]", "", raw))
    for s, text in step_inputs:
        if not any(str(w["path"]) == path for w in s.writes):
            continue
        if any(f and f in text for f in forms):
            return True
    return False


def _changed_lines(old: str, new: str) -> list[int]:
    a, b = old.splitlines(), new.splitlines()
    out: list[int] = []
    for tag, _i1, _i2, j1, j2 in difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes():
        if tag in ("replace", "insert"):
            out.extend(range(j1 + 1, j2 + 1))
    return out


def _exempt_lines(lines: list[str]) -> set[int]:
    out, level = set(), None
    in_code = False
    for i, ln in enumerate(lines, 1):
        if ln.strip().startswith("```"):
            in_code = not in_code
            out.add(i)
            continue
        if in_code:
            out.add(i)
            continue
        h = re.match(r"^\s{0,3}(#{1,6})\s", ln)
        if h:
            lv = len(h.group(1))
            if level is not None and lv <= level:
                level = None
            if EXEMPT_HEADINGS.match(ln):
                level = lv
                out.add(i)
                continue
        if level is not None:
            out.add(i)
        if i < len(lines) and re.match(r"^\s*\|?\s*:?-{3,}", lines[i]) and "|" in ln:
            out.add(i)                            # 表格的標題列
        if re.match(r"^\s*\d+[.)]\s", ln):
            pass
    return out


def _strip_code(line: str) -> str:
    line = re.sub(r"`[^`]*`", " ", line)
    line = re.sub(r"^\s*\d+[.)]\s", " ", line)      # 清單編號
    return re.sub(r"#[0-9a-fA-F]{3,8}\b", " ", line)  # 色碼


def _sentence_around(text: str, s: int, e: int) -> str:
    a = max(text.rfind(".", 0, s), text.rfind("\n", 0, s)) + 1
    b_candidates = [x for x in (text.find(".", e), text.find("\n", e)) if x >= 0]
    b = min(b_candidates) if b_candidates else len(text)
    return text[a:b].strip()[:120]


def _command_of(tr: Trace, s: Step) -> str:
    obj = tr.input_obj(s)
    if isinstance(obj, dict):
        for k in ("command", "cmd", "script"):
            v = obj.get(k)
            if isinstance(v, list):
                v = " ".join(map(str, v))
            if isinstance(v, str) and v.strip():
                return v.strip()
    return tr.input_text(s).strip()[:500]


def _norm_cmd(cmd: str) -> str:
    words = re.findall(r"[^\s\"']+", cmd or "")
    first_file = next((w for w in words[1:] if re.search(r"\.\w{1,5}$", w)), "")
    return f"{words[0] if words else ''} {first_file}".strip()


def evidence_for(rec: Recorder, *, platform: str, session: str, final_text: str | None = None,
                 today: _dt.date | None = None) -> dict[str, Any]:
    return Evidence(rec, platform=platform, session=session, final_text=final_text,
                    today=today).run()
