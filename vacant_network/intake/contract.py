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


def _numeric_columns(p: pathlib.Path) -> list[str]:
    """CSV 裡每一格（非空）都讀得成數字的欄。只當提示用，**不會**變成主張。"""
    import csv
    import io
    try:
        rows = list(csv.DictReader(io.StringIO(p.read_text(encoding="utf-8")),
                                   delimiter="\t" if p.suffix.lower() == ".tsv" else ","))
    except (OSError, UnicodeDecodeError, csv.Error):
        return []
    if not rows:
        return []
    out = []
    for col in rows[0].keys() or []:
        vals = [(r.get(col) or "").strip() for r in rows]
        vals = [v for v in vals if v]
        try:
            if vals and all(math.isfinite(float(v.replace(",", ""))) for v in vals):
                out.append(col)
        except ValueError:
            continue
    return out


def quick(base_dir: pathlib.Path, *, deliverable: list[str], inputs: list[str] | None = None,
          must: list[str] | None = None, must_not: list[str] | None = None,
          headings: list[str] | None = None, totals: list[str] | None = None,
          report: str | None = None, task_id: str | None = None, objective: str = "",
          destination: str = "dir:.vacant/published") -> tuple[dict[str, Any], dict[str, Any]]:
    """`vacant contract quick`：一般人真的會寫的那種契約——交什麼、給了什麼（會被釘住）、哪幾件事一定要對。

    這支在架構裡承重什麼（`decisions/DECISION_20260924_ACCOUNTABLE_TRACE.md` §八「延後」那一項；
    `ops/accountability/design_review_fable.md` Q5-3）：追緝只在有契約時才有東西可追，而 `scaffold` 只驗「檔案在、
    沒夾帶憑證」——那不是人在意的事。規則：**只有人寫出來的才是必要的主張**；不替人猜（CSV 裡看起來像數字的欄
    只列成提示，不會自己變成一條主張）；欄名在寫契約的當下就對過 CSV 的表頭（寫錯在這裡炸，不是在驗收時才變成
    「不知道」）。回傳 `(契約, 摘要)`；摘要說清楚驗了什麼、**沒驗什麼**。

    誠實邊界：`--must` 是「有出現這段字」，不是「這段話是對的」；`--total` 只驗報告裡寫的那一個總數等於重算的欄總和。
    """
    base = pathlib.Path(base_dir).resolve()
    deliverable = [d.strip() for d in deliverable if d and d.strip()]
    if not deliverable:
        raise ContractError(["say what the deliverable is (--deliverable report.md)"])
    probs: list[str] = []
    ins: dict[str, dict[str, str]] = {}
    in_paths: dict[str, pathlib.Path] = {}
    for raw_path in inputs or []:
        ap = (base / raw_path).resolve() if not pathlib.Path(raw_path).is_absolute() \
            else pathlib.Path(raw_path).resolve()
        try:
            rel = ap.relative_to(base).as_posix()
        except ValueError:
            probs.append(f"input {raw_path}: must be inside the project ({base})")
            continue
        if not ap.is_file():
            probs.append(f"input {raw_path}: no such file")
            continue
        stem = re.sub(r"[^A-Za-z0-9_]", "_", ap.stem).strip("_") or "input"
        stem = stem if re.match(r"[A-Za-z0-9]", stem) else f"in_{stem}"
        name, k = stem, 2
        while name in ins:
            name, k = f"{stem}_{k}", k + 1
        ins[name] = {"path": rel}
        in_paths[name] = ap
    literal = [d for d in deliverable if not any(ch in d for ch in "*?[")]
    target = report or (literal[0] if len(literal) == 1 and len(deliverable) == 1 else None)
    wants_text = bool(must or must_not or headings)
    if (wants_text or totals) and not target:
        probs.append("say which file the checks read (--report PATH): the deliverable is not a "
                     "single file")
    claims: list[dict[str, Any]] = [
        {"id": "deliverable_present", "verifier": "exists", "params": {"paths": deliverable},
         "required": True, "authority": "requirement",
         "description": "the deliverable files exist"},
        {"id": "no_secrets_shipped", "verifier": "forbid_paths",
         "params": {"paths": ["**/.env", "**/.env.*", "**/*.pem", "**/id_rsa*", "**/auth.json"]},
         "required": True, "authority": "requirement",
         "description": "no credential files in the deliverable"},
    ]
    if wants_text and target:
        params: dict[str, Any] = {"path": target}
        if must:
            params["must_contain"] = [re.escape(x) for x in must]
        if must_not:
            params["must_not_contain"] = [re.escape(x) for x in must_not]
        if headings:
            params["required_headings"] = list(headings)
        bits = [f"contains {x!r}" for x in must or []] + \
            [f"does not contain {x!r}" for x in must_not or []] + \
            [f"has a heading {x!r}" for x in headings or []]
        claims.append({"id": QUICK_TEXT_ID, "verifier": "text", "params": params,
                       "required": True, "authority": "requirement",
                       "description": f"{target} " + "; ".join(bits)})
    used: set[str] = set()
    for spec in totals or []:
        name, _, col = spec.rpartition(":")
        csvs = [n for n, p in in_paths.items() if p.suffix.lower() in (".csv", ".tsv")]
        if not name:
            if len(csvs) != 1:
                probs.append(f"--total {spec}: say which input (NAME:COLUMN); CSV inputs: "
                             f"{', '.join(csvs) or 'none (add --input data.csv)'}")
                continue
            name = csvs[0]
        elif name not in in_paths:
            by_path = [n for n, p in in_paths.items()
                       if ins[n]["path"] == name or p.name == name]
            if len(by_path) != 1:
                probs.append(f"--total {spec}: no input named {name!r} (inputs: "
                             f"{', '.join(in_paths) or 'none'})")
                continue
            name = by_path[0]
        tsv = in_paths[name].suffix.lower() == ".tsv"
        header = _csv_header(in_paths[name], "\t" if tsv else ",")
        if col not in header:
            probs.append(f"--total {spec}: {ins[name]['path']} has no column {col!r} "
                         f"(columns: {', '.join(header) or 'none'})")
            continue
        used.add(name)
        cid = re.sub(r"[^A-Za-z0-9_.-]", "_", f"{QUICK_TOTAL_PREFIX}{name}_{col}")[:128]
        claims.append({"id": cid, "verifier": "csv_total", "authority": "fact", "required": True,
                       "params": {"csv": f"input:{name}", "column": col, "report": target,
                                  **({"delimiter": "\t"} if tsv else {})},
                       "description": f"the total stated in {target} equals the sum of column "
                                      f"{col!r} of {ins[name]['path']}"})
    if probs:
        raise ContractError(probs)
    tid = task_id or re.sub(r"[^A-Za-z0-9._-]", "-",
                            f"{base.name}-{pathlib.Path(target or deliverable[0]).stem}").strip("-.")
    tid = tid if _ID_RE.match(tid or "") else "task"
    raw = scaffold(tid[:128], objective=objective, deliverable=deliverable,
                   destination=destination)
    raw["inputs"] = ins
    raw["claims"] = claims
    hints = [f"{ins[n]['path']} has numeric column(s) {', '.join(cols)} — add "
             f"--total {n}:{cols[0]} if the deliverable states their total"
             for n, p in in_paths.items() if n not in used
             for cols in [_numeric_columns(p)] if cols]
    summary = {"task_id": raw["task_id"], "report": target,
               "checks": [{"id": c["id"], "what": c["description"], "required": c["required"],
                           "authority": c["authority"]} for c in claims],
               "inputs": {n: v["path"] for n, v in ins.items()},
               "not_checked": "anything about whether the deliverable is right beyond these "
                              "checks — add --must/--total, or `vacant flag FILE:LINE` a wrong "
                              "place after the fact",
               "hints": hints}
    return raw, summary


def _csv_header(p: pathlib.Path, delimiter: str = ",") -> list[str]:
    import csv
    import io
    try:
        first = p.read_text(encoding="utf-8").splitlines()[:1]
        return next(csv.reader(io.StringIO(first[0]), delimiter=delimiter)) if first else []
    except (OSError, UnicodeDecodeError, csv.Error, StopIteration):
        return []


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
                        "exclude": [".git/**", ".vacant/**", "node_modules/**"]},
        "inputs": {},
        "claims": [
            {"id": "deliverable_present", "verifier": "exists",
             "params": {"paths": deliverable or ["**"]}, "required": True,
             "authority": "requirement",
             "description": "the deliverable files exist"},
            {"id": "no_secrets_shipped", "verifier": "forbid_paths",
             "params": {"paths": ["**/.env", "**/.env.*", "**/*.pem", "**/id_rsa*",
                                  "**/auth.json"]},
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
