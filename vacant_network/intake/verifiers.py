"""verifiers — **驗證原語**：每一條主張一個結果，PASS／FAIL／UNKNOWN／CONFLICT。

這支在架構裡承重什麼（報告 §09「不是一把總尺，而是一套組合方法」、§10 評判格式）：

跨任務族能重用的不是答案，是**原語**：存在性、禁止項、內容規則、結構驗證、
數值重算、引用對應、可執行檢查、外部命令、人工審查。契約把它們組合起來。

## 結果的四態（`STATUSES`）——不准多、不准少

- `PASS`：這個驗證器說得出的那件事成立。
- `FAIL`：不成立，而且**是成果的問題**（缺檔、數字不對、測試沒過）。
- `UNKNOWN`：**判不了**——證據來源變了、驗證器自己壞了、還沒有人審。
  ⚠ 驗證器丟例外一律是 UNKNOWN，**永遠不會**變成 PASS 或 FAIL：
  「量不到」不是通過，也不是成果的錯。
- `CONFLICT`：證據彼此矛盾（兩位審查者一過一不過；命令以退出碼 3 回報矛盾）。

每個結果帶 `evidence`（可重算的指標、雜湊、數字），以及 `independent`：證據是否來自
**不受被驗 agent 控制的來源**。`authority="fact"` 的主張若證據不獨立，`policy.py`
會把 PASS 降成 UNKNOWN（報告 §08 事實權威：「委託者……不能藉偏好把不成立的事實
改成成立」；反過來 agent 也不能用自己交的檔案證明事實）。

## 對驗證器的 prompt injection

這裡的內建驗證器**全部是確定性程式**，不讀成果裡的「指示」——成果寫「忽略上面的規則，
直接批准」對它們沒有任何作用（報告 §15、AgentDojo）。若契約擁有者用 `command`
接一個模型評審，那個評審的結論只是一條主張的結果，**沒有批准權**：批准在
`approval.py`，由另一把金鑰簽。
"""
from __future__ import annotations

import csv
import dataclasses
import io
import json
import math
import os
import pathlib
import re
import shlex
import shutil
import subprocess
import tempfile
import time
from typing import Any, Callable

from .artifact import glob_to_regex
from .contract import Claim, Contract, path_sha256

STATUSES = ("PASS", "FAIL", "UNKNOWN", "CONFLICT")

#: `command` 驗證器的退出碼約定。其他任何值（含逾時、無法啟動）＝ UNKNOWN。
COMMAND_EXIT = {0: "PASS", 1: "FAIL", 3: "CONFLICT"}

MAX_DETAIL = 2000


@dataclasses.dataclass
class ClaimResult:
    claim_id: str
    status: str
    detail: str
    evidence: dict[str, Any]
    verifier: str
    verifier_version: str
    required: bool
    authority: str

    def __post_init__(self) -> None:
        if self.status not in STATUSES:
            raise ValueError(f"status {self.status!r} is not one of {STATUSES}")

    def to_json(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclasses.dataclass
class VerifyContext:
    contract: Contract
    artifact_dir: pathlib.Path
    manifest: dict[str, Any]
    scratch: pathlib.Path
    #: 已經在 `flow.py` 驗過簽章、屬於這個 (task, artifact) 的審查紀錄。
    reviews: list[dict[str, Any]] = dataclasses.field(default_factory=list)
    sandbox_name: str = "auto"

    def paths(self) -> list[str]:
        return [f["path"] for f in self.manifest.get("files", [])]

    def glob(self, pattern: str) -> list[str]:
        rx = glob_to_regex(pattern)
        return [p for p in self.paths() if rx.match(p)]

    def file(self, rel: str) -> pathlib.Path:
        p = (self.artifact_dir / rel).resolve()
        if self.artifact_dir.resolve() not in (p, *p.parents):
            raise ValueError(f"path {rel!r} escapes the artifact")
        return p

    def pinned_input(self, name: str) -> tuple[pathlib.Path | None, str]:
        """回 `(路徑, 問題)`；問題非空 ⇒ 這個輸入不能當證據（呼叫端回 UNKNOWN）。"""
        try:
            p = self.contract.input_path(name)
        except KeyError as e:
            return None, str(e)
        pin = self.contract.input_pin(name)
        if not p.exists():
            return None, f"input {name!r} ({p}) does not exist"
        if not pin:
            return None, (f"input {name!r} is not pinned; run `vacant contract lock` so "
                          f"its content cannot change under the verdict")
        actual = path_sha256(p)
        if actual != pin:
            return None, (f"input {name!r} changed since it was pinned "
                          f"({pin[:12]}… → {actual[:12]}…)")
        return p, ""


Verifier = Callable[[VerifyContext, Claim], tuple[str, str, dict[str, Any]]]


@dataclasses.dataclass(frozen=True)
class VerifierSpec:
    fn: Verifier
    version: str
    params: tuple[str, ...]
    summary: str


VERIFIERS: dict[str, VerifierSpec] = {}


def verifier(name: str, *, version: str, params: tuple[str, ...], summary: str):
    def deco(fn: Verifier) -> Verifier:
        VERIFIERS[name] = VerifierSpec(fn=fn, version=version, params=params,
                                       summary=summary)
        return fn
    return deco


def _clip(s: str, n: int = MAX_DETAIL) -> str:
    return s if len(s) <= n else s[: n // 2] + "…[cut]…" + s[-(n // 2):]


def _unknown_params(claim: Claim, allowed: tuple[str, ...]) -> list[str]:
    return sorted(set(claim.params) - set(allowed))


class ParamError(ValueError):
    """契約給的參數型別不對 ⇒ 這條主張 UNKNOWN（驗證器設定錯，不是成果的錯）。"""


def _str_list(claim: Claim, key: str, *, required: bool = False) -> list[str]:
    """`paths: "id_rsa"` 這種手滑會被當成六個單字元樣式逐字迭代 ⇒ 一律要求真的 list[str]。"""
    v = claim.params.get(key)
    if v is None:
        if required:
            raise ParamError(f"{claim.verifier}: params.{key} is required")
        return []
    if not (isinstance(v, list) and all(isinstance(x, str) and x for x in v)):
        raise ParamError(f"{claim.verifier}: params.{key} must be a list of non-empty "
                         f"strings, got {type(v).__name__}")
    if required and not v:
        raise ParamError(f"{claim.verifier}: params.{key} is empty")
    return v


def _str_param(claim: Claim, key: str, *, required: bool = True) -> str | None:
    v = claim.params.get(key)
    if v is None or v == "":
        if required:
            raise ParamError(f"{claim.verifier}: params.{key} is required")
        return None
    if not isinstance(v, str):
        raise ParamError(f"{claim.verifier}: params.{key} must be a string")
    return v


def _num_param(claim: Claim, key: str, default: float, *, minimum: float | None = None
               ) -> float:
    v = claim.params.get(key, default)
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        raise ParamError(f"{claim.verifier}: params.{key} must be a finite number")
    if minimum is not None and v < minimum:
        raise ParamError(f"{claim.verifier}: params.{key} must be >= {minimum}")
    return float(v)


# ── 存在性／禁止項／釘死 ───────────────────────────────────────────────

@verifier("exists", version="2", params=("paths", "min_count"),
          summary="each glob matches at least min_count files in the deliverable")
def _exists(ctx: VerifyContext, claim: Claim):
    pats = _str_list(claim, "paths", required=True)
    n_min = int(_num_param(claim, "min_count", 1, minimum=1))
    missing = []
    counts = {}
    for p in pats:
        hits = ctx.glob(p)
        counts[p] = len(hits)
        if len(hits) < n_min:
            missing.append(f"{p} (found {len(hits)}, need {n_min})")
    ev = {"counts": counts, "independent": True}
    if missing:
        return "FAIL", "missing from the deliverable: " + ", ".join(missing), ev
    return "PASS", f"all {len(pats)} pattern(s) present", ev


@verifier("forbid_paths", version="2", params=("paths",),
          summary="no deliverable file matches any of the globs")
def _forbid(ctx: VerifyContext, claim: Claim):
    pats = _str_list(claim, "paths", required=True)   # 空清單不是「沒有禁止項」是設定錯
    bad = sorted({p for pat in pats for p in ctx.glob(pat)})
    ev = {"matched": bad[:50], "independent": True}
    if bad:
        return "FAIL", "forbidden files in the deliverable: " + ", ".join(bad[:10]), ev
    return "PASS", "no forbidden files", ev


@verifier("sha256_pin", version="2", params=("path", "sha256"),
          summary="a deliverable file has exactly this content hash")
def _pin(ctx: VerifyContext, claim: Claim):
    rel = _str_param(claim, "path")
    want = _str_param(claim, "sha256")
    if not re.fullmatch(r"[0-9a-f]{64}", str(want)):
        raise ParamError("sha256_pin: params.sha256 must be 64 lowercase hex characters")
    got = {f["path"]: f["sha256"] for f in ctx.manifest.get("files", [])}.get(rel)
    ev = {"expected": want, "actual": got, "independent": True}
    if got is None:
        return "FAIL", f"{rel} is not in the deliverable", ev
    if got != want:
        return "FAIL", f"{rel} has sha256 {got[:12]}…, expected {str(want)[:12]}…", ev
    return "PASS", f"{rel} matches the pinned hash", ev


# ── 文字內容規則 ─────────────────────────────────────────────────────

#: ATX 標題。`[ \t]` 不是 `\s`：`\s+` 會跨行，一個單獨的 `#` 接下一段就被算成標題。
_HEADING_RE = re.compile(r"^[ \t]{0,3}#{1,6}[ \t]+(.*?)[ \t]*#*[ \t]*$", re.M)
_FENCE_RE = re.compile(r"^[ \t]{0,3}(```|~~~)")


def _headings(txt: str) -> list[str]:
    """圍欄程式碼區塊裡的 `# 註解` 不是標題。"""
    out, fence = [], None
    for line in txt.splitlines():
        m = _FENCE_RE.match(line)
        if m:
            fence = None if fence == m.group(1) else (fence or m.group(1))
            continue
        if fence is None:
            h = _HEADING_RE.match(line)
            if h:
                out.append(h.group(1).strip().lower())
    return out


def show_rx(rx: str) -> str:
    """給人看的樣式：是一段純文字跳脫出來的（`vacant contract quick --must`）⇒ 引號裡的原文；否則 `/正規式/`。"""
    plain = re.sub(r"\\(.)", r"\1", rx, flags=re.S)
    return json.dumps(plain, ensure_ascii=False) if re.escape(plain) == rx else f"/{rx}/"


@verifier("text", version="2",
          params=("path", "must_contain", "must_not_contain", "required_headings",
                  "min_words", "max_words", "max_bytes"),
          summary="content rules on text files (regex present/absent, headings, length)")
def _text(ctx: VerifyContext, claim: Claim):
    """⚠ 形式符合不等於內容有用：這支只能說「規則沒被違反」。"""
    pat = _str_param(claim, "path")
    must = _str_list(claim, "must_contain")
    must_not = _str_list(claim, "must_not_contain")
    heads_req = _str_list(claim, "required_headings")
    files = ctx.glob(str(pat))
    if not files:
        return "FAIL", f"no file matches {pat}", {"independent": True}
    problems: list[str] = []
    per: dict[str, Any] = {}
    for rel in files:
        raw = ctx.file(rel).read_bytes()
        try:
            txt = raw.decode("utf-8")
        except UnicodeDecodeError:
            problems.append(f"{rel}: not UTF-8 text")
            continue
        words = len(txt.split())
        per[rel] = {"bytes": len(raw), "words": words}
        for rx in must:
            if not re.search(rx, txt, re.M):
                problems.append(f"{rel}: does not contain {show_rx(rx)}")
        for rx in must_not:
            m = re.search(rx, txt, re.M)
            if m:
                problems.append(f"{rel}: contains forbidden {show_rx(rx)} at offset {m.start()}")
        heads = _headings(txt)
        for h in heads_req:
            if h.strip().lower() not in heads:
                problems.append(f"{rel}: missing heading {h!r}")
        mn, mx = claim.params.get("min_words"), claim.params.get("max_words")
        if mn is not None and words < int(mn):
            problems.append(f"{rel}: {words} words < min {mn}")
        if mx is not None and words > int(mx):
            problems.append(f"{rel}: {words} words > max {mx}")
        mb = claim.params.get("max_bytes")
        if mb is not None and len(raw) > int(mb):
            problems.append(f"{rel}: {len(raw)} bytes > max {mb}")
    ev = {"files": per, "problems": problems[:50], "independent": True}
    if problems:
        return "FAIL", "; ".join(problems[:8]), ev
    return "PASS", f"{len(files)} file(s) satisfy the text rules", ev


# ── 結構驗證 ─────────────────────────────────────────────────────────

@verifier("json_schema", version="2", params=("path", "schema", "schema_input"),
          summary="a JSON file validates against a JSON Schema")
def _json_schema(ctx: VerifyContext, claim: Claim):
    from jsonschema import Draft202012Validator
    from jsonschema.exceptions import SchemaError
    from jsonschema.validators import validator_for

    rel = _str_param(claim, "path")
    schema = claim.params.get("schema")
    if claim.params.get("schema_input"):
        p, why = ctx.pinned_input(claim.params["schema_input"])
        if p is None:
            return "UNKNOWN", why, {}
        schema = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(schema, dict):
        return "UNKNOWN", "json_schema: no schema given", {}
    # 依 schema 自己宣告的 `$schema` 選草案（draft-07 的 `dependencies` 在 2020-12 裡會被
    # 安靜忽略）；沒宣告 ⇒ 2020-12。`format` 要真的檢查（預設只是註記）。
    cls = validator_for(schema, default=Draft202012Validator)
    try:
        cls.check_schema(schema)
    except SchemaError as e:
        return "UNKNOWN", f"the contract's schema is invalid: {e.message}", {}
    if rel not in ctx.paths():
        return "FAIL", f"{rel} is not in the deliverable", {"independent": True}

    def _no_constant(tok: str) -> Any:
        raise ValueError(f"{tok} is not valid JSON")

    try:
        doc = json.loads(ctx.file(rel).read_text(encoding="utf-8"),
                         parse_constant=_no_constant)   # NaN／Infinity 不是 JSON，比較永遠為假
    except (ValueError, UnicodeDecodeError) as e:
        return "FAIL", f"{rel} is not valid JSON: {e}", {"independent": True}
    validator = cls(schema, format_checker=cls.FORMAT_CHECKER)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    msgs = [f"{'/'.join(map(str, e.path)) or '(root)'}: {e.message}" for e in errs[:20]]
    ev = {"n_errors": len(errs), "independent": True, "errors": msgs}
    if errs:
        return "FAIL", "; ".join(msgs[:5]), ev
    return "PASS", f"{rel} validates", ev


# ── 數值重算 ─────────────────────────────────────────────────────────

#: 「total」要是一個字（`Subtotal` 不算），中間的間隔有上限（成果是不可信的輸入，
#: 無上限的 `[^0-9]*` 在 `total total total …` 上是平方時間）。
_DEFAULT_TOTAL_RE = r"(?i)(?<![A-Za-z])total(?![A-Za-z])[^0-9\n-]{0,80}(-?[0-9][0-9,]*(?:\.[0-9]+)?)"
_THOUSANDS_RE = re.compile(r"-?[0-9]{1,3}(?:,[0-9]{3})+(?:\.[0-9]+)?")


def _number(text: str) -> float | None:
    """嚴格的數字：`1,234.5` 的逗號只能是千分位（`1,5` 不是 15，是看不懂 ⇒ None）；
    NaN／inf 一律看不懂——`abs(x - nan) > tol` 永遠為假，會讓任何數字都「相符」。"""
    t = text.strip()
    if "," in t:
        if not _THOUSANDS_RE.fullmatch(t):
            return None
        t = t.replace(",", "")
    if not re.fullmatch(r"-?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][-+]?[0-9]+)?", t):
        return None
    v = float(t)
    return v if math.isfinite(v) else None


@verifier("csv_total", version="2",
          params=("csv", "column", "report", "pattern", "tolerance", "delimiter"),
          summary="a number stated in the report equals the recomputed column total")
def _csv_total(ctx: VerifyContext, claim: Claim):
    """重算，不是相信。`csv` 為 `input:<name>` ⇒ 證據獨立（委託者的資料）；
    為成果裡的路徑 ⇒ 不獨立（agent 自己給的資料，事實權威的主張會被降成 UNKNOWN）。"""
    src = str(_str_param(claim, "csv"))
    col = str(_str_param(claim, "column"))
    report = str(_str_param(claim, "report"))
    delim = _str_param(claim, "delimiter", required=False) or ","
    independent = src.startswith("input:")
    if independent:
        p, why = ctx.pinned_input(src[len("input:"):])
        if p is None:
            return "UNKNOWN", why, {}
        data = p.read_text(encoding="utf-8")
    else:
        if src not in ctx.paths():
            return "FAIL", f"{src} is not in the deliverable", {"independent": False}
        data = ctx.file(src).read_text(encoding="utf-8")
    cells: list[float] = []
    for row in csv.DictReader(io.StringIO(data), delimiter=delim):
        if col not in row:
            return "UNKNOWN", f"column {col!r} not in the CSV header", {}
        raw_cell = (row[col] or "").strip()
        if raw_cell == "":
            continue
        v = _number(raw_cell)
        if v is None:
            return "UNKNOWN", (f"cell {row[col]!r} in column {col!r} is not a finite number "
                               f"this verifier can read (decimal comma? NaN?)"), {}
        cells.append(v)
    total, n = math.fsum(cells), len(cells)
    if report not in ctx.paths():
        return "FAIL", f"report {report} is not in the deliverable", {"independent": independent}
    text = ctx.file(report).read_text(encoding="utf-8")
    pattern = _str_param(claim, "pattern", required=False) or _DEFAULT_TOTAL_RE
    found = [m.group(1) for m in re.finditer(pattern, text)]
    ev: dict[str, Any] = {"recomputed": total, "rows": n, "independent": independent,
                          "source": src}
    if not found:
        return "FAIL", "the report does not state the total", ev
    vals = [_number(x) for x in found]
    if any(v is None for v in vals):
        return "UNKNOWN", f"the report's total {found!r} is not a number this verifier reads", ev
    if len({v for v in vals}) > 1:
        return "UNKNOWN", (f"the report states {len(set(vals))} different totals "
                           f"({', '.join(found[:5])}); set params.pattern to say which one"), ev
    claimed = float(vals[0])  # type: ignore[arg-type]
    ev["claimed"] = claimed
    # 預設容差是相對的：一百萬列 0.01 加總的浮點誤差不該讓正確的 10,000.00 被退件。
    tol = _num_param(claim, "tolerance", 1e-9 * max(1.0, abs(total)), minimum=0)
    if abs(claimed - total) > tol:
        return "FAIL", f"report says {claimed:g}, recomputed {total:g}", ev
    return "PASS", f"report total {claimed:g} matches the recomputed {total:g}", ev


# ── 引用對應 ─────────────────────────────────────────────────────────

#: 註腳引用 `[^id]`（不含行首的定義 `[^id]:`）與 pandoc 引用群組 `[@a; @b, p. 3]`。
_FOOTNOTE_RE = re.compile(r"\[\^([A-Za-z0-9_.:-]+)\](?!:)")
_BRACKET_RE = re.compile(r"\[([^\[\]\n]*@[^\[\]\n]*)\]")
_PANDOC_ID_RE = re.compile(r"(?<![\w.])-?@([A-Za-z0-9_][A-Za-z0-9_.:-]*[A-Za-z0-9_])")
MIN_QUOTE_CHARS = 8


def _citations_in(text: str) -> list[str]:
    out = list(_FOOTNOTE_RE.findall(text))
    for grp in _BRACKET_RE.findall(text):
        out += _PANDOC_ID_RE.findall(grp)
    return out


def _norm_ws(s: str) -> str:
    return " ".join(s.split())


@verifier("citations_resolve", version="2",
          params=("path", "sources", "min_citations", "require_quotes", "snapshots_input"),
          summary="every citation in the document resolves to a listed source "
                  "(and, optionally, its quote appears verbatim in a snapshot)")
def _citations(ctx: VerifyContext, claim: Claim):
    """⚠ **引用存在不等於引用支持結論**（報告 §09）。這支只驗三件事：
    每個引用記號都對得到來源清單裡的一筆；來源有 http(s) 網址；（選配）引文在
    快照裡逐字出現。快照若是成果自己帶的 ⇒ `independent=False`。
    """
    rel = _str_param(claim, "path")
    src_rel = _str_param(claim, "sources")
    if rel not in ctx.paths():
        return "FAIL", f"{rel} is not in the deliverable", {"independent": True}
    if src_rel not in ctx.paths():
        return "FAIL", f"sources file {src_rel} is not in the deliverable", {"independent": True}
    text = ctx.file(rel).read_text(encoding="utf-8")
    try:
        sources = json.loads(ctx.file(src_rel).read_text(encoding="utf-8"))
    except ValueError as e:
        return "FAIL", f"{src_rel} is not valid JSON: {e}", {"independent": True}
    if isinstance(sources, dict):
        sources = sources.get("sources", [])
    by_id = {str(s.get("id")): s for s in sources if isinstance(s, dict)}
    cited = _citations_in(text)
    uniq = sorted(set(cited))
    problems: list[str] = []
    n_min = int(claim.params.get("min_citations", 1))
    if len(cited) < n_min:
        problems.append(f"{len(cited)} citation(s), need at least {n_min}")
    snap_dir = None
    # 獨立 ＝ 引文被**委託者釘住的快照**核對過。只看成果自己的 sources.json（網址從來不抓）
    # 或成果自己帶的快照 ⇒ 證據全是 agent 給的 ⇒ 不獨立（事實主張會被降成 UNKNOWN）。
    independent = False
    if claim.params.get("require_quotes") and claim.params.get("snapshots_input"):
        snap_dir, why = ctx.pinned_input(str(claim.params["snapshots_input"]))
        if snap_dir is None:
            return "UNKNOWN", why, {}
        independent = True
    for cid in uniq:
        s = by_id.get(cid)
        if s is None:
            problems.append(f"[{cid}] is cited but not in {src_rel}")
            continue
        url = str(s.get("url", ""))
        if not re.match(r"^https?://", url):
            problems.append(f"[{cid}] has no http(s) url")
        if claim.params.get("require_quotes"):
            quote = s.get("quote")
            if not isinstance(quote, str) or len(_norm_ws(quote).replace(" ", "")) \
                    < MIN_QUOTE_CHARS:
                problems.append(f"[{cid}] has no quote (at least {MIN_QUOTE_CHARS} "
                                f"non-space characters)")
                continue
            if snap_dir is not None:
                sp = snap_dir / f"{cid}.txt"
                snap = sp.read_text(encoding="utf-8") if sp.is_file() else None
            else:
                snap_rel = s.get("snapshot")
                snap = (ctx.file(snap_rel).read_text(encoding="utf-8")
                        if snap_rel and snap_rel in ctx.paths() else None)
            if snap is None:
                problems.append(f"[{cid}] has no snapshot to check the quote against")
            elif _norm_ws(str(quote)) not in _norm_ws(snap):
                problems.append(f"[{cid}] quote does not appear in its snapshot")
    ev = {"n_citations": len(cited), "cited_ids": uniq[:100], "n_sources": len(by_id),
          "problems": problems[:50], "independent": independent}
    if problems:
        return "FAIL", "; ".join(problems[:8]), ev
    return "PASS", f"{len(uniq)} cited source(s) resolve", ev


# ── 可執行檢查 ───────────────────────────────────────────────────────

@verifier("python_checks", version="3", params=("suite", "timeout_s"),
          summary="a pinned directory of test_*.py check_* functions passes "
                  "(declared-case reconciliation, vrun/acceptance.py)")
def _python_checks(ctx: VerifyContext, claim: Claim):
    """⚠ **防意外，不防惡意**：受測的程式碼與檢查跑在同一個直譯器裡，一份有意偽造的成果
    可以改寫檢查的結果（`vrun/acceptance.py` docstring 的同一條邊界）。成果不可信時，
    用 `command` 接一個**行程外**的評測器，或用 `suitespec` 的資料化規約。
    這裡擋得住的是：宣告了卻沒跑完、提早離開、回傳 False、以及成果帶的 shell／python
    啟動檔（`.bash_profile`、`usercustomize`——沙箱以 hermetic 模式執行）。"""
    from ..vrun import acceptance
    from ..vrun.sandbox import SandboxInfraError, make_sandbox

    suite = str(claim.params.get("suite") or "")
    if not suite.startswith("input:"):
        return "UNKNOWN", ("python_checks.suite must be `input:<name>`: a suite the agent "
                           "can edit is not an acceptance test"), {}
    p, why = ctx.pinned_input(suite[len("input:"):])
    if p is None:
        return "UNKNOWN", why, {}
    run_ws = ctx.scratch / f"pc_{claim.id}_ws"
    if run_ws.exists():
        shutil.rmtree(run_ws)
    shutil.copytree(ctx.artifact_dir, run_ws)
    try:
        sb, meta = make_sandbox(ctx.sandbox_name, workdir=str(ctx.scratch))
    except SystemExit as e:
        return "UNKNOWN", f"sandbox unavailable: {e}", {}
    sb.hermetic = True   # 成果裡的 .bash_profile／usercustomize 不准在檢查之前執行
    try:
        res = acceptance.run_suite(sb, run_ws, p, suite="visible", task_id=ctx.contract.task_id,
                                   verify_root=ctx.scratch / f"pc_{claim.id}_v",
                                   timeout_s=float(claim.params.get("timeout_s", 30)))
    except SandboxInfraError as e:
        return "UNKNOWN", f"sandbox infrastructure error: {e}", {}
    ev = {"passed": res["passed"], "total": res["total"], "complete": res.get("complete"),
          "result_sha256": res["result_sha256"], "suite_sha256": res.get("suite_sha256"),
          "sandbox": meta.get("backend") if isinstance(meta, dict) else None,
          "independent": True}
    if res.get("empty_reason"):
        return "UNKNOWN", str(res["empty_reason"]), ev
    if res["all_pass"]:
        return "PASS", f"{res['passed']}/{res['total']} checks passed", ev
    return "FAIL", _clip(acceptance.render_failures(res)), ev


@verifier("command", version="2", params=("argv", "timeout_s", "sandbox", "env"),
          summary="an owner-supplied command: exit 0 PASS, 1 FAIL, 3 CONFLICT, else UNKNOWN "
                  "(a python script that crashes also exits 1: map your own errors to 2)")
def _command(ctx: VerifyContext, claim: Claim):
    """命令來自契約（可信），成果不可信 ⇒ 要跑成果裡的程式碼請設 `sandbox: "auto"`。

    命令在**成果的一份新拷貝**裡執行（改不到正本），環境變數只有：
    `PATH`、`HOME`（暫存，**不在成果裡**）、`LANG`、`VACANT_ARTIFACT_DIR`、每個已驗證的
    `VACANT_INPUT_<NAME>`，外加契約裡 `env` 明寫的——**有沒有沙箱都一樣**
    （沙箱後端以 hermetic 模式執行：不讀成果裡的 shell 啟動檔、不載 python user site；
    `bwrap` 另外把釘住的輸入唯讀掛進去）。

    任何一個契約輸入沒釘住或變了 ⇒ UNKNOWN：命令可能讀它，而我們不知道它讀的是哪一版。
    ⚠ 退出碼 1 同時是「成果不合格」與「python 未捕捉的例外」——委託者的腳本要自己
    把內部錯誤轉成 1／3 以外的碼（例如 2），否則腳本壞掉會被記成成果的錯。
    """
    argv = claim.params.get("argv")
    if not (isinstance(argv, list) and argv and all(isinstance(a, str) for a in argv)):
        return "UNKNOWN", "command.argv must be a non-empty list of strings", {}
    run_ws = ctx.scratch / f"cmd_{claim.id}_ws"
    if run_ws.exists():
        shutil.rmtree(run_ws)
    shutil.copytree(ctx.artifact_dir, run_ws)
    shared = {"LANG": "C.UTF-8", "VACANT_ARTIFACT_DIR": str(run_ws)}
    binds: list[pathlib.Path] = []
    for name in (ctx.contract.raw.get("inputs") or {}):
        p, why = ctx.pinned_input(name)
        if p is None:
            return "UNKNOWN", f"cannot run the command on unverified inputs: {why}", {}
        shared[f"VACANT_INPUT_{re.sub(r'[^A-Za-z0-9]', '_', name).upper()}"] = str(p)
        binds.append(p)
    user_env = claim.params.get("env") or {}
    if not isinstance(user_env, dict):
        raise ParamError("command: params.env must be an object")
    for k, v in user_env.items():
        shared[str(k)] = str(v)
    timeout = _num_param(claim, "timeout_s", 60, minimum=0.1)
    t0 = time.time()
    if claim.params.get("sandbox", "none") != "none":
        from ..vrun.sandbox import SandboxInfraError, make_sandbox
        try:
            sb, _meta = make_sandbox(str(claim.params["sandbox"]), workdir=str(ctx.scratch))
            sb.hermetic = True
            r = sb.run(shlex.join(argv), workspace=run_ws, timeout_s=timeout,
                       env=shared, ro_binds=tuple(binds))
        except (SystemExit, SandboxInfraError) as e:
            return "UNKNOWN", f"sandbox unavailable: {e}", {}
        rc, out, timed_out = r.rc, (r.stdout or "") + (r.stderr or ""), r.timed_out
    else:
        home = ctx.scratch / f"cmd_{claim.id}_home"
        home.mkdir(parents=True, exist_ok=True)
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(home),
               "PYTHONNOUSERSITE": "1", **shared}
        try:
            cp = subprocess.run(argv, cwd=run_ws, env=env, capture_output=True, text=True,
                                timeout=timeout, stdin=subprocess.DEVNULL)
            rc, out, timed_out = cp.returncode, cp.stdout + cp.stderr, False
        except subprocess.TimeoutExpired as e:
            rc, timed_out = None, True
            out = (e.stdout or b"").decode("utf-8", "replace") if isinstance(e.stdout, bytes) \
                else str(e.stdout or "")
        except OSError as e:
            return "UNKNOWN", f"command could not start: {e}", {"argv0": argv[0]}
    ev = {"rc": rc, "timed_out": timed_out, "wall_ms": int((time.time() - t0) * 1000),
          "argv0": argv[0], "independent": True}
    status = "UNKNOWN" if timed_out or rc is None else COMMAND_EXIT.get(rc, "UNKNOWN")
    why = ("timed out" if timed_out else f"exit {rc}")
    return status, _clip(f"{why}: {out.strip()}"), ev


# ── 人工審查（品質權威）──────────────────────────────────────────────

@verifier("review", version="2", params=("reviewers", "min_reviews"),
          summary="signed human reviews of this exact artifact: none → UNKNOWN, "
                  "split → CONFLICT")
def _review(ctx: VerifyContext, claim: Claim):
    """審查綁在 **(task, claim, artifact_sha256)**：成果改一個位元組，舊審查就不算。
    分歧保留成 CONFLICT，不取平均（報告 §08）。"""
    allowed = set(_str_list(claim, "reviewers"))
    need = int(_num_param(claim, "min_reviews", 1, minimum=1))
    rs = [r for r in ctx.reviews if r.get("claim_id") == claim.id
          and (not allowed or r.get("reviewer") in allowed)]
    latest: dict[str, dict[str, Any]] = {}
    for r in sorted(rs, key=lambda r: r.get("ts_ms", 0)):
        latest[str(r.get("reviewer"))] = r
    verdicts = {k: v.get("verdict") for k, v in latest.items()}
    local = sorted(k for k, v in latest.items() if v.get("same_account"))
    ev = {"reviews": [{"reviewer": k, "verdict": v, "same_account": k in local}
                      for k, v in sorted(verdicts.items())],
          "independent": not local}
    if len(latest) < need:
        return "UNKNOWN", f"awaiting review ({len(latest)}/{need})", ev
    vals = set(verdicts.values())
    note = (f" (signed with this machine's own reviewer key — same account as the verifier: "
            f"{', '.join(local)})") if local else ""
    if vals == {"pass"}:
        return "PASS", f"{len(latest)} reviewer(s) passed it{note}", ev
    if vals == {"fail"}:
        reasons = "; ".join(str(v.get("reason", "")) for v in latest.values())[:400]
        return "FAIL", f"reviewers failed it: {reasons}", ev
    return "CONFLICT", "reviewers disagree: " + ", ".join(
        f"{k}={v}" for k, v in sorted(verdicts.items())), ev


# ── 執行 ─────────────────────────────────────────────────────────────

def run_claim(ctx: VerifyContext, claim: Claim) -> ClaimResult:
    spec = VERIFIERS.get(claim.verifier)

    def mk(status: str, detail: str, ev: dict[str, Any], version: str) -> ClaimResult:
        return ClaimResult(claim_id=claim.id, status=status, detail=_clip(str(detail)),
                           evidence=ev, verifier=claim.verifier, verifier_version=version,
                           required=claim.required, authority=claim.authority)

    if spec is None:
        return mk("UNKNOWN", f"no verifier named {claim.verifier!r}", {}, "-")
    bad = _unknown_params(claim, spec.params)
    if bad:
        return mk("UNKNOWN", f"unknown params for {claim.verifier}: {', '.join(bad)}", {},
                  spec.version)
    try:
        status, detail, ev = spec.fn(ctx, claim)
    except ParamError as e:
        status, detail, ev = "UNKNOWN", f"contract error: {e}", {}
    except Exception as e:  # noqa: BLE001 — 驗證器壞掉是 UNKNOWN，永遠不是 PASS／FAIL
        status, detail, ev = "UNKNOWN", f"verifier error: {type(e).__name__}: {e}", {}
    return mk(status, detail, ev, spec.version)


def run_all(ctx: VerifyContext) -> list[ClaimResult]:
    """契約裡每一條主張**恰好一個結果**，依契約順序——完整性由建構保證。"""
    return [run_claim(ctx, c) for c in ctx.contract.claims]


def scratch_dir(prefix: str = "vacant-verify-") -> pathlib.Path:
    return pathlib.Path(tempfile.mkdtemp(prefix=prefix))
