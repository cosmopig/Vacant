"""contract — **任務契約**：要驗什麼、證據從哪來、誰說了算、交到哪裡。

這支在架構裡承重什麼（`decisions/DECISION_20260924_UNIVERSAL_INTAKE.md` §二；
外部質疑報告 §13「一份可實作的通用任務契約」）：

契約是收件口唯一的判準來源。它**版本固定、以內容雜湊識別**（`contract_sha256`）：
裁決、批准、放行全部綁在那個雜湊上 ⇒ 委託者事後改需求就是一份新契約，舊任務的成功
定義不會被改寫。

## 形狀（JSON；`.toml` 也收，內容相同）

    {
      "schema": "vacant-contract/1",
      "task_id": "report-001",
      "version": 1,
      "objective": "比較三個方案並給出建議",
      "owner": "alice",
      "deliverable": {"include": ["report.md", "sources/**"], "exclude": []},
      "inputs": {"sales": {"path": "data/sales.csv", "sha256": "…"}},
      "claims": [
        {"id": "totals_recomputed", "verifier": "csv_total",
         "params": {...}, "required": true, "authority": "fact"}
      ],
      "unknown_policy": "hold",
      "conflict_policy": "escalate",
      "release": {"destination": "dir:published", "requires_approval": false,
                  "approvers": [], "replace": false},
      "effects": {"deny_commands": ["git push"], "protect_paths": []},
      "attempts": {"max": 1},
      "hooks": {"stop_check": true, "max_feedback_rounds": 3, "submit_on_end": true}
    }

**未知的欄位一律拒絕**（不是忽略）。理由是 vacant_hm `GATE_MUST_EXIST_R146` 那一課：
刪掉（或拼錯）一個門檻鍵，檢查就安靜地消失，舊版仍宣布全過。契約寫錯要在載入時炸，
不是在出貨後才發現少驗了一項。

## `inputs`：事實權威的來源必須不在 agent 手上

`authority="fact"` 的主張，證據應來自**委託者固定下來的輸入**（原始資料、驗收套件），
而不是 agent 自己交出來的檔案。`inputs` 以 sha256 釘住（`vacant contract lock`
會補上）；驗證時重算，對不上 ⇒ 那一項是 `UNKNOWN`（證據來源變了），不是 PASS。

## 誠實邊界

1. 契約能表達的只有「我們有驗證器的主張」。沒有可信觀測方法的主張，應該寫成
   `verifier="review"`（人工），而不是用一段模型自評補成證明（報告 §09 末段）。
2. `suitespec.py` 那句「客戶把 2+2 寫成 5 就交 5」只適用於 `authority="requirement"`
   的輸入輸出規約；**需求不能改寫事實**（見 `policy.py` 的衝突規則）。
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import math
import pathlib
import re
import shlex
import tomllib
from typing import Any

from ..canonical import canonical_bytes

CONTRACT_SCHEMA = "vacant-contract/1"

#: 契約檔的預設位置（由近到遠找，停在 `.git` 那一層）。
CONTRACT_NAMES = (".vacant/contract.json", ".vacant/contract.toml",
                  "vacant.contract.json", "vacant.contract.toml")

AUTHORITIES = ("requirement", "fact", "quality", "approval")
UNKNOWN_POLICIES = ("hold", "reject")
CONFLICT_POLICIES = ("escalate", "reject")

_TOP_KEYS = {"schema", "task_id", "version", "objective", "owner", "deliverable",
             "inputs", "claims", "unknown_policy", "conflict_policy", "release",
             "effects", "attempts", "hooks", "notes"}
_CLAIM_KEYS = {"id", "verifier", "params", "required", "authority", "description",
               "hidden"}
_RELEASE_KEYS = {"destination", "requires_approval", "approvers", "replace"}
_EFFECT_KEYS = {"deny_commands", "protect_paths"}
_ATTEMPT_KEYS = {"max"}
_HOOK_KEYS = {"stop_check", "max_feedback_rounds", "submit_on_end"}
_DELIV_KEYS = {"include", "exclude"}
_INPUT_KEYS = {"path", "sha256", "description"}

_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class ContractError(ValueError):
    """契約不合法。訊息列出**全部**問題，不是只列第一個。"""

    def __init__(self, problems: list[str]):
        self.problems = list(problems)
        super().__init__("; ".join(self.problems))


@dataclasses.dataclass(frozen=True)
class Claim:
    id: str
    verifier: str
    params: dict[str, Any]
    required: bool
    authority: str
    description: str
    #: `True` ⇒ 回饋給 agent 時只說「沒過」，不附細節（例：委託者保留的隱藏驗收）。
    hidden: bool = False


@dataclasses.dataclass(frozen=True)
class Contract:
    raw: dict[str, Any]
    path: pathlib.Path | None
    base_dir: pathlib.Path
    claims: tuple[Claim, ...]

    @property
    def task_id(self) -> str:
        return str(self.raw["task_id"])

    @property
    def version(self) -> int:
        return int(self.raw.get("version", 1))

    @property
    def sha256(self) -> str:
        return contract_sha256(self.raw)

    @property
    def unknown_policy(self) -> str:
        return str(self.raw.get("unknown_policy", "hold"))

    @property
    def conflict_policy(self) -> str:
        return str(self.raw.get("conflict_policy", "escalate"))

    @property
    def include(self) -> list[str]:
        return list((self.raw.get("deliverable") or {}).get("include") or ["**"])

    @property
    def exclude(self) -> list[str]:
        return list((self.raw.get("deliverable") or {}).get("exclude") or [])

    @property
    def release(self) -> dict[str, Any]:
        return dict(self.raw.get("release") or {})

    @property
    def effects(self) -> dict[str, Any]:
        return dict(self.raw.get("effects") or {})

    @property
    def hooks(self) -> dict[str, Any]:
        h = {"stop_check": True, "max_feedback_rounds": 3, "submit_on_end": True}
        h.update(self.raw.get("hooks") or {})
        return h

    @property
    def max_attempts(self) -> int:
        return int((self.raw.get("attempts") or {}).get("max", 1))

    def input_path(self, name: str) -> pathlib.Path:
        spec = (self.raw.get("inputs") or {}).get(name)
        if spec is None:
            raise KeyError(f"contract has no input named {name!r}")
        return (self.base_dir / spec["path"]).resolve()

    def input_pin(self, name: str) -> str | None:
        spec = (self.raw.get("inputs") or {}).get(name) or {}
        return spec.get("sha256")


def contract_sha256(raw: dict[str, Any]) -> str:
    """內容雜湊。canonical JSON ⇒ 排版、鍵順序、JSON/TOML 格式都不影響。"""
    return hashlib.sha256(canonical_bytes(raw)).hexdigest()


def path_sha256(p: pathlib.Path) -> str:
    """檔案＝內容 sha256；目錄＝(相對路徑, 內容 sha256) 排序後的雜湊。

    目錄輸入用在驗收套件（`python_checks` 的 `suite`）：套件被改一個字，釘住的雜湊
    就對不上 ⇒ 那一項變 UNKNOWN，而不是用被改過的套件判 PASS。
    """
    p = pathlib.Path(p)
    if p.is_file():
        h = hashlib.sha256()
        with p.open("rb") as f:
            for b in iter(lambda: f.read(1 << 16), b""):
                h.update(b)
        return h.hexdigest()
    if p.is_dir():
        rows = []
        for q in sorted(x for x in p.rglob("*") if x.is_file()):
            if "__pycache__" in q.parts:
                continue
            rows.append([q.relative_to(p).as_posix(), path_sha256(q)])
        return hashlib.sha256(canonical_bytes(rows)).hexdigest()
    raise FileNotFoundError(str(p))


def validate(raw: Any, *, known_verifiers: set[str] | None = None) -> list[str]:
    """回傳全部問題（空清單＝合法）。`known_verifiers=None` ⇒ 不檢查驗證器名稱。"""
    probs: list[str] = []
    if not isinstance(raw, dict):
        return ["contract must be a JSON object"]
    for k in sorted(set(raw) - _TOP_KEYS):
        probs.append(f"unknown top-level key {k!r} (typos are errors, not ignored)")
    if raw.get("schema") != CONTRACT_SCHEMA:
        probs.append(f"schema must be {CONTRACT_SCHEMA!r}")
    tid = raw.get("task_id")
    if not isinstance(tid, str) or not _ID_RE.match(tid):
        probs.append("task_id must match [A-Za-z0-9][A-Za-z0-9._-]{0,127}")
    ver = raw.get("version", 1)
    if not isinstance(ver, int) or isinstance(ver, bool) or ver < 1:
        probs.append("version must be a positive integer")
    for key, allowed in (("unknown_policy", UNKNOWN_POLICIES),
                         ("conflict_policy", CONFLICT_POLICIES)):
        if key in raw and raw[key] not in allowed:
            probs.append(f"{key} must be one of {allowed}")
    probs += _check_section(raw, "deliverable", _DELIV_KEYS)
    deliv = raw.get("deliverable") or {}
    for k in ("include", "exclude"):
        v = deliv.get(k)
        if v is not None and not (isinstance(v, list) and all(isinstance(x, str) for x in v)):
            probs.append(f"deliverable.{k} must be a list of glob strings")
    probs += _check_section(raw, "release", _RELEASE_KEYS)
    rel = raw.get("release") or {}
    if "destination" in rel and not isinstance(rel["destination"], str):
        probs.append("release.destination must be a string like 'dir:<path>' or 'git:<repo>#<branch>'")
    if "approvers" in rel and not (isinstance(rel["approvers"], list)
                                   and all(isinstance(a, str) for a in rel["approvers"])):
        probs.append("release.approvers must be a list of trusted approver names")
    if rel.get("requires_approval") and not rel.get("approvers"):
        probs.append("release.requires_approval needs at least one name in release.approvers")
    probs += _check_section(raw, "effects", _EFFECT_KEYS)
    probs += _check_section(raw, "attempts", _ATTEMPT_KEYS)
    att = raw.get("attempts") or {}
    if "max" in att and (not isinstance(att["max"], int) or isinstance(att["max"], bool)
                         or not 1 <= att["max"] <= 10):
        probs.append("attempts.max must be an integer in 1..10")
    probs += _check_section(raw, "hooks", _HOOK_KEYS)
    inputs = raw.get("inputs") or {}
    if not isinstance(inputs, dict):
        probs.append("inputs must be an object of name -> {path, sha256}")
        inputs = {}
    for name, spec in inputs.items():
        if not _ID_RE.match(str(name)):
            probs.append(f"input name {name!r} is not a valid id")
        if not isinstance(spec, dict) or "path" not in spec:
            probs.append(f"input {name!r} needs a path")
            continue
        for k in sorted(set(spec) - _INPUT_KEYS):
            probs.append(f"input {name!r}: unknown key {k!r}")
    claims = raw.get("claims")
    if not isinstance(claims, list) or not claims:
        probs.append("claims must be a non-empty list (a contract that checks nothing "
                     "cannot accept anything)")
        claims = []
    seen: set[str] = set()
    n_required = 0
    for i, c in enumerate(claims):
        where = f"claims[{i}]"
        if not isinstance(c, dict):
            probs.append(f"{where} must be an object")
            continue
        for k in sorted(set(c) - _CLAIM_KEYS):
            probs.append(f"{where}: unknown key {k!r}")
        cid = c.get("id")
        if not isinstance(cid, str) or not _ID_RE.match(cid):
            probs.append(f"{where}.id must be a valid id")
        elif cid in seen:
            probs.append(f"duplicate claim id {cid!r}")
        else:
            seen.add(cid)
        v = c.get("verifier")
        if not isinstance(v, str):
            probs.append(f"{where}.verifier must be a string")
        elif known_verifiers is not None and v not in known_verifiers:
            probs.append(f"{where}.verifier {v!r} is not a known verifier "
                         f"({', '.join(sorted(known_verifiers))})")
        if "params" in c and not isinstance(c["params"], dict):
            probs.append(f"{where}.params must be an object")
        if "authority" in c and c["authority"] not in AUTHORITIES:
            probs.append(f"{where}.authority must be one of {AUTHORITIES}")
        for bk in ("required", "hidden"):
            if bk in c and not isinstance(c[bk], bool):
                probs.append(f"{where}.{bk} must be true/false")
        if c.get("required", True):
            n_required += 1
    if claims and n_required == 0:
        probs.append("at least one claim must be required")
    return probs


def _check_section(raw: dict, key: str, allowed: set[str]) -> list[str]:
    sec = raw.get(key)
    if sec is None:
        return []
    if not isinstance(sec, dict):
        return [f"{key} must be an object"]
    return [f"{key}: unknown key {k!r}" for k in sorted(set(sec) - allowed)]


def parse(raw: dict[str, Any], *, path: pathlib.Path | None = None,
          base_dir: pathlib.Path | None = None,
          known_verifiers: set[str] | None = None) -> Contract:
    probs = validate(raw, known_verifiers=known_verifiers)
    if probs:
        raise ContractError(probs)
    claims = tuple(
        Claim(id=c["id"], verifier=c["verifier"], params=dict(c.get("params") or {}),
              required=bool(c.get("required", True)),
              authority=str(c.get("authority", "requirement")),
              description=str(c.get("description", "")),
              hidden=bool(c.get("hidden", False)))
        for c in raw["claims"])
    if base_dir is None:
        if path is None:
            base_dir = pathlib.Path.cwd()
        else:
            base_dir = (path.parent.parent if path.parent.name == ".vacant"
                        else path.parent)
    return Contract(raw=raw, path=path, base_dir=pathlib.Path(base_dir).resolve(),
                    claims=claims)


def read_raw(path: pathlib.Path) -> dict[str, Any]:
    text = pathlib.Path(path).read_text(encoding="utf-8")
    if str(path).endswith(".toml"):
        return tomllib.loads(text)
    return json.loads(text)


def load(path: str | pathlib.Path, *, known_verifiers: set[str] | None = None) -> Contract:
    p = pathlib.Path(path).resolve()
    if known_verifiers is None:
        from .verifiers import VERIFIERS
        known_verifiers = set(VERIFIERS)
    try:
        raw = read_raw(p)
    except (OSError, ValueError, tomllib.TOMLDecodeError) as e:
        raise ContractError([f"cannot read contract {p}: {e}"]) from e
    return parse(raw, path=p, known_verifiers=known_verifiers)


def find(start: str | pathlib.Path) -> pathlib.Path | None:
    """由 `start` 往上找契約檔，遇到含 `.git` 的那一層為止（含該層）。"""
    d = pathlib.Path(start).resolve()
    if d.is_file():
        d = d.parent
    for cur in (d, *d.parents):
        for name in CONTRACT_NAMES:
            cand = cur / name
            if cand.is_file():
                return cand
        if (cur / ".git").exists():
            return None
    return None


def lock(path: str | pathlib.Path) -> dict[str, str]:
    """把每個 input 的 sha256 釘進契約檔（只補沒有的；已釘的若對不上就報錯）。

    回傳 `{input_name: sha256}`。已釘而對不上 ⇒ `ContractError`——
    默默覆寫釘子等於把「來源被換掉」洗成正常。
    """
    p = pathlib.Path(path).resolve()
    if str(p).endswith(".toml"):
        raise ContractError(["lock only rewrites JSON contracts; pin sha256 by hand in TOML"])
    raw = read_raw(p)
    c = parse(raw, path=p)
    pins: dict[str, str] = {}
    probs: list[str] = []
    for name, spec in (raw.get("inputs") or {}).items():
        try:
            actual = path_sha256(c.input_path(name))
        except FileNotFoundError:
            probs.append(f"input {name!r}: {spec['path']} does not exist")
            continue
        if spec.get("sha256") and spec["sha256"] != actual:
            probs.append(f"input {name!r} is pinned to {spec['sha256'][:12]}… but is now "
                         f"{actual[:12]}… (refusing to re-pin silently)")
            continue
        spec["sha256"] = actual
        pins[name] = actual
    if probs:
        raise ContractError(probs)
    p.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return pins


#: `vacant contract quick` 產生的主張 id（改了會讓舊契約的報告對不上，別動）
QUICK_TEXT_ID, QUICK_TOTAL_PREFIX = "says_what_you_asked", "total_"
#: 讀不出文字的繳付物：`--must`／`--total` 放在它們上面，每一次都只會是 FAIL 或「不知道」
_BINARY_EXT = frozenset({".docx", ".doc", ".pdf", ".xlsx", ".xls", ".pptx", ".ppt", ".odt",
                         ".png", ".jpg", ".jpeg", ".gif", ".zip", ".gz", ".tar"})
#: 看起來像「總計列」的第一格（匯出的 CSV 常在最後一列放總數；`csv_total` 會把它也加進去）
_TOTAL_ROW_RE = re.compile(r"(?i)^\s*(grand\s*)?(sub)?totals?\b|^\s*sum\b|^\s*(合計|總計|总计|小計|小计)")


def _read_table(p: pathlib.Path) -> tuple[list[str], list[dict[str, Any]], str]:
    """(表頭, 列, 分隔符)——和 `csv_total` 同一種讀法（UTF-8、`csv.DictReader`）。讀不了 ⇒ ContractError。"""
    import csv
    import io
    delim = "\t" if p.suffix.lower() == ".tsv" else ","
    try:
        text = p.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise ContractError([f"{p.name} is not UTF-8 text (the check reads it as UTF-8; "
                             f"save it as UTF-8 first)"]) from None
    try:
        rd = csv.DictReader(io.StringIO(text), delimiter=delim)
        rows = list(rd)
        header = list(rd.fieldnames or [])
    except csv.Error as e:
        raise ContractError([f"{p.name}: not a readable CSV ({e})"]) from None
    return header, rows, delim


def _numeric_columns(p: pathlib.Path) -> list[str]:
    """`csv_total` 讀得動的欄（每一格非空的都讀得成數字，用的是驗證器自己的讀法）。只當提示，**不會**變成主張。"""
    from .verifiers import _number
    try:
        header, rows, _d = _read_table(p)
    except ContractError:
        return []
    out = []
    for col in header:
        vals = [str(r.get(col) or "").strip() for r in rows if isinstance(r.get(col), str)]
        vals = [v for v in vals if v]
        if vals and all(_number(v) is not None for v in vals):
            out.append(col)
    return out


def _rel_in(base: pathlib.Path, raw_path: str, cwd: pathlib.Path) -> str | None:
    """人打的路徑（相對於他現在所在的目錄，或絕對）→ 專案裡的相對 POSIX 路徑；在專案外 ⇒ None。"""
    ap = pathlib.Path(raw_path)
    ap = (ap if ap.is_absolute() else cwd / ap).resolve()
    try:
        return ap.relative_to(base).as_posix()
    except ValueError:
        return None


def _norm_deliverable(base: pathlib.Path, d: str, cwd: pathlib.Path) -> str | None:
    """人打的繳付物（`./report.md`、絕對路徑、`out/`、`docs/*.md`）→ 契約裡的樣式（相對於專案的 POSIX；
    目錄 ＝ 它底下的全部）。`exists`／隔離區比對的是這個字串，寫成 `./report.md` 會永遠對不上。"""
    d = d.strip()
    if not any(ch in d for ch in "*?[") and (d.endswith("/") or (cwd / d).is_dir()):
        d = d.rstrip("/") + "/**"
    parts = d.split("/")
    k = next((n for n, x in enumerate(parts) if any(ch in x for ch in "*?[")), len(parts))
    prefix = "/".join(parts[:k]) or "."
    rel = _rel_in(base, prefix, cwd)
    if rel is None:
        return None
    rest = "/".join(parts[k:])
    if rel in ("", "."):
        return rest or None
    return rel + ("/" + rest if rest else "")


def _total_spec(spec: str, csv_inputs: dict[str, dict[str, Any]]) -> tuple[str, str, str | None]:
    """`[INPUT:]COLUMN[=LABEL]` → (輸入名, 欄, 標籤)。INPUT 是輸入名或它的路徑；欄名裡可以有 `:`。"""
    body, eq, label = spec.partition("=")
    label_s = label.strip() if eq else None
    for name, info in csv_inputs.items():
        for key in (name, info["path"], pathlib.Path(info["path"]).name):
            if body.startswith(key + ":"):
                return name, body[len(key) + 1:], label_s
    if len(csv_inputs) == 1:
        return next(iter(csv_inputs)), body, label_s
    if ":" in body:
        raise ContractError([f"--total {spec}: no CSV input named {body.split(':')[0]!r} "
                             f"(CSV inputs: {', '.join(csv_inputs) or 'none'})"])
    raise ContractError([f"--total {spec}: say which input (INPUT:COLUMN); CSV inputs: "
                         f"{', '.join(csv_inputs) or 'none (add --input data.csv)'}"])


def _label_pattern(label: str) -> str:
    """「<標籤> … 數字」：標籤後面（同一行、80 字以內、中間沒有別的數字）的第一個數字。

    邊界擋的是**整個詞**（字母／數字／底線都算詞的一部分），不是只擋字母——否則
    `amount` 會配到 `amount_usd`（`_` 不是字母）、`q1` 會配到 `q12`（數字不是字母）。
    """
    lead = r"(?<![A-Za-z0-9_])" if label[:1].isalnum() or label[:1] == "_" else ""
    tail = r"(?![A-Za-z0-9_])" if label[-1:].isalnum() or label[-1:] == "_" else ""
    return (r"(?i)" + lead + re.escape(label) + tail
            + r"[^0-9\n-]{0,80}(-?[0-9][0-9,]*(?:\.[0-9]+)?)")


def _labels_collide(a: str, b: str) -> bool:
    """同一份報告裡，兩個 `--total` 標籤如果一個包含另一個（不分大小寫），驗證器的
    寬鬆比對就分不清是哪一個——`amount` 也會配到 `net amount` 裡的那個數字。"""
    a, b = a.lower(), b.lower()
    return a in b or b in a


_QUICK_EXCLUDE = [".git/**", ".vacant/**", "node_modules/**"]       # 和 `scaffold` 的 exclude 同一份
#: `no_secrets_shipped` 擋的樣式（`scaffold` 與 `quick` 共用同一份，不要各寫一次分岔）
_FORBID_PATTERNS = ["**/.env", "**/.env.*", "**/*.pem", "**/id_rsa*", "**/auth.json"]


def _existing_forbidden(base: pathlib.Path, include: list[str], exclude: list[str]) -> list[str]:
    """這份 deliverable（含 exclude）現在就會挑進去的檔案裡，哪些是 `no_secrets_shipped`
    擋的。用的是跟 `vacant submit` 隔離區同一份 `artifact.collect`，不是自己重寫一套 glob——
    這樣「寫契約時算出來的」和「之後真的驗的」永遠是同一個答案。"""
    from . import artifact as _A
    chosen, _skipped = _A.collect(base, include, exclude)
    return sorted(rel for rel, _p in chosen if _A.matches(rel, _FORBID_PATTERNS))


def quick(base_dir: pathlib.Path, *, deliverable: list[str], inputs: list[str] | None = None,
          must: list[str] | None = None, must_not: list[str] | None = None,
          headings: list[str] | None = None, totals: list[str] | None = None,
          report: str | None = None, task_id: str | None = None, objective: str = "",
          destination: str = "dir:.vacant/published", exclude: list[str] | None = None,
          cwd: pathlib.Path | None = None
          ) -> tuple[dict[str, Any], dict[str, Any]]:
    """`vacant contract quick`：一般人真的會寫的那種契約——交什麼、給了什麼（會被釘住）、哪幾件事一定要對。

    這支在架構裡承重什麼（`decisions/DECISION_20260924_ACCOUNTABLE_TRACE.md` §八「延後」那一項；
    `ops/accountability/design_review_fable.md` Q5-3）：追緝只在有契約時才有東西可追，而 `scaffold` 只驗「檔案在、
    沒夾帶憑證」——那不是人在意的事。規則：**人寫的才是必要的主張**（另外只有兩條安全底線：繳付物在、沒夾帶憑證檔）；
    不替人猜（CSV 裡讀得成數字的欄只列成提示）；寫錯在寫契約的當下就炸——欄名、讀不動的欄、總計列、
    讀不出文字的繳付物、在繳付物外面的報告、agent 永遠滿足不了的主張（輸入同時是繳付物、繳付物裡已經有
    憑證檔）。回傳 `(契約, 摘要)`；摘要的每一條都照驗證器**真的怎麼驗**說
    （2026-09-25 對抗審查 32 條，`ops/accountability/review_contract_quick/FINDINGS.md`）。

    誠實邊界：`--must` 是「有出現這段字」，不是「這段話是對的」；`--total` 驗的是報告裡標籤後面**每一個**符合的
    數字都等於重算的欄總和（不只第一個；標籤預設是 `Total`，且同一份報告裡兩個標籤不能互相包含，否則寬鬆比對
    分不清是哪一個）；只讀 `--report` 那一個檔；總計列偵測只擋**有標籤**的那一列，數字剛好等於總和但沒標籤的
    只警告不擋。
    """
    from . import artifact as _A
    base = pathlib.Path(base_dir).resolve()
    here = pathlib.Path(cwd).resolve() if cwd else base
    probs: list[str] = []
    warnings: list[str] = []
    dl: list[str] = []
    for d in deliverable or []:
        if not d or not d.strip():
            continue
        n = _norm_deliverable(base, d, here)
        if n is None or n.startswith(".vacant"):
            probs.append(f"deliverable {d}: must be inside the project ({base}) and not .vacant/")
        else:
            dl.append(n)
    if not dl and not probs:
        raise ContractError(["say what the deliverable is (--deliverable report.md)"])
    for flag, vals in (("--must", must), ("--must-not", must_not), ("--heading", headings)):
        if any(not (v or "").strip() for v in vals or []):
            probs.append(f"{flag}: empty text checks nothing")
    full_exclude = list(_QUICK_EXCLUDE) + [x for x in (exclude or []) if (x or "").strip()]
    ins: dict[str, dict[str, str]] = {}
    in_paths: dict[str, pathlib.Path] = {}
    for raw_path in inputs or []:
        rel = _rel_in(base, raw_path, here)
        if rel is None:
            probs.append(f"input {raw_path}: must be inside the project ({base})")
            continue
        ap = base / rel
        if not ap.is_file():
            probs.append(f"input {raw_path}: no such file ({ap})")
            continue
        if dl and _A.matches(rel, dl) and not _A.matches(rel, full_exclude):
            probs.append(f"input {raw_path}: is also inside the deliverable ({', '.join(dl)}); "
                         f"the hook write-protects task inputs, so the agent could never change "
                         f"{rel} to satisfy the contract (give the agent a copy under a different "
                         f"name, or drop --input {raw_path} if it is meant to be edited)")
            continue
        stem = re.sub(r"[^A-Za-z0-9_]", "_", ap.stem).strip("_") or "input"
        stem = stem if re.match(r"[A-Za-z0-9]", stem) else f"in_{stem}"
        name, k = stem[:60], 2
        while name in ins:
            name, k = f"{stem[:60]}_{k}", k + 1
        ins[name] = {"path": rel}
        in_paths[name] = ap
    if dl:
        secret_hits = _existing_forbidden(base, dl, full_exclude)
        if secret_hits:
            probs.append("the deliverable already contains file(s) the default no_secrets_shipped "
                         "check forbids: " + ", ".join(secret_hits) + " — add --exclude PATTERN "
                         "(repeatable, e.g. --exclude '**/.env.example') to leave them out of the "
                         "deliverable, or move/rename them first; quick never excludes them for you")
    literal = [d for d in dl if not any(ch in d for ch in "*?[")]
    target: str | None = None
    if report:
        target = _rel_in(base, report, here)
        if target is None or any(ch in target for ch in "*?[") or (base / target).is_dir():
            probs.append(f"--report {report}: must be one file inside the project")
            target = None
        elif not _A.matches(target, dl) or _A.matches(target, _QUICK_EXCLUDE):
            probs.append(f"--report {report}: is not part of the deliverable "
                         f"({', '.join(dl)}); the checks read the delivered files")
            target = None
    elif len(literal) == 1 and len(dl) == 1:
        target = literal[0]
    wants_text = bool(must or must_not or headings)
    if (wants_text or totals) and not target and not any("--report" in x for x in probs):
        probs.append("say which file the checks read (--report PATH): the deliverable is not a "
                     "single file")
    if target and (wants_text or totals) and pathlib.Path(target).suffix.lower() in _BINARY_EXT:
        probs.append(f"{target}: the checks read text; a {pathlib.Path(target).suffix} file "
                     f"cannot be checked this way (deliver a .md/.txt next to it)")
    claims: list[dict[str, Any]] = [
        {"id": "deliverable_present", "verifier": "exists", "params": {"paths": dl},
         "required": True, "authority": "requirement",
         "description": "the deliverable files exist"},
        {"id": "no_secrets_shipped", "verifier": "forbid_paths",
         "params": {"paths": list(_FORBID_PATTERNS)},
         "required": True, "authority": "requirement",
         "description": "no credential-looking files in the deliverable (.env, .env.*, *.pem, "
                        "id_rsa*, auth.json — .env.example counts too)"},
    ]
    heads = [re.sub(r"^\s*#+\s*", "", h).strip() for h in headings or []]
    if wants_text and target:
        params: dict[str, Any] = {"path": target}
        if must:
            params["must_contain"] = [re.escape(x) for x in must]
        if must_not:
            params["must_not_contain"] = [re.escape(x) for x in must_not]
        if heads:
            params["required_headings"] = heads
        bits = [f"contains the text {x!r}" for x in must or []] + \
            [f"does not contain the text {x!r}" for x in must_not or []] + \
            [f"has a '#' heading {x!r}" for x in heads]
        claims.append({"id": QUICK_TEXT_ID, "verifier": "text", "params": params,
                       "required": True, "authority": "requirement",
                       "description": f"{target} (only this file is read) " + "; ".join(bits)})
    csv_inputs = {n: {"path": ins[n]["path"]} for n, p in in_paths.items()
                  if p.suffix.lower() in (".csv", ".tsv")}
    used: set[str] = set()
    parsed: list[tuple[str, str, str | None, str]] = []
    for spec in totals or []:
        try:
            name, col, label = _total_spec(spec, csv_inputs)
        except ContractError as e:
            probs += e.problems
            continue
        if label == "":
            probs.append(f"--total {spec}: empty label")
            continue
        parsed.append((name, col, label, spec))
    same_report = len(parsed) > 1
    ids: set[str] = set()
    used_labels: list[tuple[str, str]] = []      # (標籤, 它的 --total spec)，只用來查同報告碰撞
    for name, col, label, spec in parsed:
        try:
            header, rows, delim = _read_table(in_paths[name])
        except ContractError as e:
            probs += e.problems
            continue
        exact = col if col in header else None
        if exact is None:
            near = [h for h in header if h.replace("﻿", "").strip() == col.strip()]
            exact = near[0] if len(near) == 1 else None      # 同一欄：表頭多了 BOM／空白
        if exact is None:
            probs.append(f"--total {spec}: {ins[name]['path']} has no column {col!r} "
                         f"(columns: {', '.join(repr(h) for h in header) or 'none'})")
            continue
        from .verifiers import _number
        cells = [(n + 2, str(r.get(exact) or "").strip()) for n, r in enumerate(rows)
                 if isinstance(r.get(exact), str)]
        bad = [(ln, c) for ln, c in cells if c and _number(c) is None]
        if bad:
            probs.append(f"--total {spec}: the check cannot read {bad[0][1]!r} in column "
                         f"{exact!r} (line {bad[0][0]} of {ins[name]['path']}) as a number")
            continue
        # 有標籤的總計列（Total/合計/…）：加了就是雙算，一定擋。數字剛好等於前面總和但**沒有標籤**
        # 的那種（10/20/30 這種正常資料常常撞到）只警告、照樣寫契約——見 #17。
        labelled_totals_row = [n + 2 for n, r in enumerate(rows)
                               if any(isinstance(v, str) and _TOTAL_ROW_RE.match(v)
                                      for k, v in r.items() if k != exact)]
        if labelled_totals_row:
            probs.append(f"--total {spec}: line {labelled_totals_row[0]} of {ins[name]['path']} "
                         f"looks like a totals row (its first column is labelled 'Total'/'合計'/…); "
                         f"the check adds every row, so it would count it twice — remove that row "
                         f"from the input first")
            continue
        nums = [x for x in (_number(c) for _ln, c in cells if c) if x is not None]
        if len(nums) > 2 and abs(nums[-1] - math.fsum(nums[:-1])) < 1e-9 * max(1.0, abs(nums[-1])):
            warnings.append(f"{ins[name]['path']} line {cells[-1][0]} equals the sum of the rows "
                            f"above it; if it is a totals row, remove it from the input (the check "
                            f"would otherwise count it twice)")
        used.add(name)
        lab = label or (col.strip() if same_report else None)
        if same_report and lab:
            collide = next((ol for ol, _os in used_labels if _labels_collide(lab, ol)), None)
            if collide is not None:
                probs.append(f"--total {spec}: label {lab!r} and an earlier --total's label "
                             f"{collide!r} would collide in the same report (one contains the "
                             f"other, so the loose text match cannot tell them apart) — give each "
                             f"an explicit --total COLUMN=LABEL")
                used_labels.append((lab, spec))
                continue
            used_labels.append((lab, spec))
        cid = re.sub(r"[^A-Za-z0-9_.-]", "_", f"{QUICK_TOTAL_PREFIX}{name}_{col}")[:120]
        base_cid, k = cid, 2
        while cid in ids:
            cid, k = f"{base_cid}_{k}", k + 1
        ids.add(cid)
        params_t: dict[str, Any] = {"csv": f"input:{name}", "column": exact, "report": target}
        if delim != ",":
            params_t["delimiter"] = delim
        if lab:
            params_t["pattern"] = _label_pattern(lab)
        rule = (f"the number after {lab!r} in {target}" if lab else
                f"the number after 'Total' in {target} (it must be the only 'Total <number>' "
                f"there; add =LABEL to --total to use other wording)")
        claims.append({"id": cid, "verifier": "csv_total", "authority": "fact", "required": True,
                       "params": params_t,
                       "description": f"{rule} equals the sum of column {exact!r} of "
                                      f"{ins[name]['path']}"})
    if task_id is not None and not _ID_RE.match(task_id):
        probs.append(f"--task {task_id!r}: use letters, digits, '.', '_' or '-' "
                     f"(it names the task's ledger)")
    if probs:
        raise ContractError(probs)
    if task_id is None:
        # 兩個不同專案，deliverable 的檔名（甚至整份契約）都可能一模一樣（同一份作業模板）；
        # task_id 是帳本的 key，一定要把專案路徑釘進去，不能只在換不過來的字元時才加——見 #12。
        want = f"{base.name}-{pathlib.Path(target or dl[0].replace('*', 'x')).stem}"
        tid = re.sub(r"[^A-Za-z0-9._-]", "-", want).strip("-.")[:100] or "task"
        task_id = f"{tid}-{hashlib.sha256(str(base).encode()).hexdigest()[:8]}"
    raw = scaffold(task_id, objective=objective, deliverable=dl, destination=destination)
    raw["deliverable"]["exclude"] = full_exclude
    raw["inputs"] = ins
    raw["claims"] = claims
    parse(raw, path=base / ".vacant" / "contract.json")          # 寫之前先驗：不合法就不寫
    hints = [f"{ins[n]['path']} has column(s) the check can total: {', '.join(cols)} — e.g. "
             f"--total {shlex.quote(n + ':' + cols[0])}"
             for n, p in in_paths.items() if n not in used and n in csv_inputs
             for cols in [_numeric_columns(p)] if cols]
    summary = {"task_id": raw["task_id"], "report": target,
               "checks": [{"id": c["id"], "what": c["description"], "required": c["required"],
                           "authority": c["authority"]} for c in claims],
               "inputs": {n: v["path"] for n, v in ins.items()},
               "not_checked": "anything about whether the deliverable is right beyond these "
                              "checks — to add some, rerun with --replace and more --must/--total, "
                              "or `vacant flag FILE:LINE` a wrong place after the fact",
               "hints": hints, "warnings": warnings}
    return raw, summary


def scaffold(task_id: str, *, objective: str = "", deliverable: list[str] | None = None,
             destination: str = "dir:.vacant/published") -> dict[str, Any]:
    """`vacant contract init` 的起點：一個最小但**會驗東西**的契約。"""
    return {
        "schema": CONTRACT_SCHEMA,
        "task_id": task_id,
        "version": 1,
        "objective": objective,
        "owner": "",
        "deliverable": {"include": deliverable or ["**"],
                        "exclude": list(_QUICK_EXCLUDE)},
        "inputs": {},
        "claims": [
            {"id": "deliverable_present", "verifier": "exists",
             "params": {"paths": deliverable or ["**"]}, "required": True,
             "authority": "requirement",
             "description": "the deliverable files exist"},
            {"id": "no_secrets_shipped", "verifier": "forbid_paths",
             "params": {"paths": list(_FORBID_PATTERNS)},
             "required": True, "authority": "requirement",
             "description": "no credential files in the deliverable"},
        ],
        "unknown_policy": "hold",
        "conflict_policy": "escalate",
        "release": {"destination": destination, "requires_approval": False,
                    "approvers": [], "replace": False},
        "effects": {"deny_commands": [], "protect_paths": []},
        "attempts": {"max": 1},
        "hooks": {"stop_check": True, "max_feedback_rounds": 3, "submit_on_end": True},
    }
