"""這支在架構裡承重什麼：**「怎樣算對」的通用驗證器**——程式以外的任務也要有閘門，
而且 token 要可控。規格與量測在 `decisions/DECISION_20260924_GENERAL_VERIFIER_TOKEN_BUDGET.md`。

## 為什麼要有這一支

既有閘門（`vrun/acceptance.py`）只對「能跑的程式」有答案：跑使用者給的測試，
過就交付。寫作、資料整理、研究摘要、操作類任務沒有測試可跑。人類 2026-09-24：
「雖然我們也完全可以丟一個守門員去判斷，但他的判斷跟 token 都是成本跟不確定。」

本檔的答案是**三件事疊起來**，每一件都可以單獨拿掉：

  1. **先定規格再做**（`Spec`）：驗收準則在工作開始**之前**凍結，`Spec.sha256()`
     簽進收據。準則可以由使用者寫，也可以從任務描述萃取——但萃取也要在工作前做完。
     這跟 `acceptance.py`「agent 改不到那份測試」是同一條紀律，搬到非程式任務上。
  2. **確定性檢查優先的級聯**（`evaluate()`）：每一條準則先找便宜、可重算的檢查
     （字數、格式、關鍵字、JSON、**證據引文是否逐字存在於來源**……）。
     只有確定性檢查給不出答案的準則，才花 token 問 LLM 評審，而且有**每題上限**。
  3. **三值裁決**：每條準則是 `accepted`／`rejected`／`unknown`。
     **`unknown` 永遠不是通過**：整體裁決＝任一 rejected ⇒ rejected；
     全部 accepted ⇒ accepted；否則 unknown。預算用完、評審說不確定、
     評審的引文對不上 ⇒ 都是 unknown。

## 誠實邊界（改碼請保留）

1. **確定性檢查的「對」只到它自己的定義**。`word_count <= 300` 判得準的是字數，
   不是「寫得好」。規格寫錯，驗證器會很準地驗一個錯的東西（`suitegauge` 的單邊保證
   逐字適用）。
2. **LLM 評審的 accepted 仍然是意見**，不是證明。本檔能做的是：只在必要時問、
   限制它花多少、要它附一段**可逐字核對的引文**（`require_quote`），核不到就降成
   unknown。引文存在 ≠ 判斷正確，只證明它不是憑空捏造那段文字。
3. **`rejected` 與 `accepted` 的可信度不對稱**。「回應裡有一個來源沒有的數字」
   是很強的 rejected 證據；「每個數字都在來源裡」**不是** accepted 的證據。
   所以證據類檢查預設只能出 rejected 或 unknown（`numbers_supported` 的設計）。
4. **token 上限是這一支自己數的**（評審後端回報的用量），不是帳單。
   後端若有固定開銷（例如 CLI 自帶的系統提示），要另外量、另外講。
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Callable

ACCEPTED, REJECTED, UNKNOWN = "accepted", "rejected", "unknown"
VERDICTS = (ACCEPTED, REJECTED, UNKNOWN)


# ───────────────────────── 規格 ─────────────────────────

@dataclass
class Criterion:
    """一條驗收準則。

    kind:
      "check"  ——確定性檢查，`check` 是 `CHECKS` 裡的名字，`params` 是參數。
      "judge"  ——只能靠評審；`question` 是給評審的是非題（要能用 yes/no 回答）。
    `fallback_judge`：確定性檢查回 unknown 時，要不要升級給評審。
    `screen`：**反證型**檢查（只會出 rejected 或 unknown，例如 `numbers_supported`）。
      它的 unknown 意思是「沒有找到反證」，**不參與** accepted 的彙總——否則一條
      永遠給不出 accepted 的檢查會讓整份規格永遠是 unknown。它的 rejected 照樣一票否決。
    `judge_may_decide`：評審對這一條的 accepted／rejected **算不算數**。預設 False
      ＝評審只能留下理由、裁決仍是 unknown（交給人）。只有**事先量過、錯誤率低於凍結門檻**
      的準則類別才准打開（Fable 判斷 #2 Q2：RAGTruth 上評審拒絕的 precision 只有 0.68、
      IFEval 上評審讓接受者錯誤率從 2.5% 翻到 4.6%）。
    """
    id: str
    kind: str
    check: str | None = None
    params: dict = field(default_factory=dict)
    question: str | None = None
    fallback_judge: bool = False
    screen: bool = False
    judge_may_decide: bool = False

    def to_json(self) -> dict:
        return {"id": self.id, "kind": self.kind, "check": self.check,
                "params": self.params, "question": self.question,
                "fallback_judge": self.fallback_judge, "screen": self.screen,
                "judge_may_decide": self.judge_may_decide}


@dataclass
class Spec:
    """凍結的驗收規格。`sha256()` 在工作開始前算一次、簽進收據。"""
    task: str
    criteria: list[Criterion]
    judge_token_cap: int | None = None   # 每題評審 token 上限；None＝不限
    sources: dict[str, str] = field(default_factory=dict)  # 名字→來源全文（證據類檢查用）

    def to_json(self) -> dict:
        return {"task": self.task, "criteria": [c.to_json() for c in self.criteria],
                "judge_token_cap": self.judge_token_cap,
                "sources_sha256": {k: hashlib.sha256(v.encode()).hexdigest()
                                   for k, v in sorted(self.sources.items())}}

    def sha256(self) -> str:
        return hashlib.sha256(json.dumps(self.to_json(), sort_keys=True,
                                         ensure_ascii=False).encode()).hexdigest()


# ───────────────────────── 確定性檢查 ─────────────────────────
# 每一支：(output_text, params, spec) -> (verdict, evidence_str)
# 回 UNKNOWN ＝ 這支檢查對這個輸入沒有答案（不是「過」）。

def _rel(n: int, relation: str, target: int) -> bool:
    return {"at least": n >= target, "less than": n < target,
            "at most": n <= target, "exactly": n == target}[relation]


def _words(text: str) -> list[str]:
    return re.findall(r"\b\w+\b", text)


def chk_word_count(text, p, spec):
    n = len(_words(text))
    ok = _rel(n, p["relation"], p["n"])
    return (ACCEPTED if ok else REJECTED), f"words={n}"


def chk_regex_count(text, p, spec):
    flags = re.M | (re.I if p.get("ignore_case") else 0) | (re.S if p.get("dotall") else 0)
    n = len(re.findall(p["pattern"], text, flags))
    ok = _rel(n, p["relation"], p["n"])
    return (ACCEPTED if ok else REJECTED), f"count={n}"


def chk_contains_all(text, p, spec):
    t = text.lower() if p.get("ignore_case", True) else text
    miss = [k for k in p["keywords"] if (k.lower() if p.get("ignore_case", True) else k) not in t]
    return (REJECTED, f"missing={miss}") if miss else (ACCEPTED, "all present")


def chk_forbids(text, p, spec):
    hits = []
    for k in p["keywords"]:
        pat = r"\b" + re.escape(k) + r"\b" if p.get("whole_word", True) else re.escape(k)
        if re.search(pat, text, re.I if p.get("ignore_case", True) else 0):
            hits.append(k)
    return (REJECTED, f"found={hits}") if hits else (ACCEPTED, "none found")


def chk_keyword_freq(text, p, spec):
    n = len(re.findall(r"\b" + re.escape(p["keyword"]) + r"\b", text, re.I))
    return (ACCEPTED if _rel(n, p["relation"], p["n"]) else REJECTED), f"count={n}"


def chk_letter_freq(text, p, spec):
    n = text.lower().count(p["letter"].lower())
    return (ACCEPTED if _rel(n, p["relation"], p["n"]) else REJECTED), f"count={n}"


def chk_case(text, p, spec):
    if p["case"] == "lower":
        ok = text == text.lower()
    else:
        ok = text == text.upper()
    return (ACCEPTED if ok else REJECTED), p["case"]


def chk_json_parses(text, p, spec):
    s = text.strip()
    s = re.sub(r"^```(?:json|Json|JSON)?\s*|\s*```$", "", s)
    try:
        json.loads(s)
        return ACCEPTED, "parses"
    except ValueError as ex:
        return REJECTED, f"json error: {ex}"


def chk_starts_ends(text, p, spec):
    s = text.strip()
    if "ends_with" in p and not s.lower().endswith(p["ends_with"].strip().lower()):
        return REJECTED, "bad ending"
    if p.get("quoted") and not (len(s) > 1 and s[0] == '"' and s[-1] == '"'):
        return REJECTED, "not wrapped in double quotes"
    if "starts_with" in p and not s.lower().startswith(p["starts_with"].strip().lower()):
        return REJECTED, "bad start"
    return ACCEPTED, "ok"


def chk_paragraphs(text, p, spec):
    parts = [x for x in re.split(p.get("sep", r"\s?\*\*\*\s?"), text) if x.strip()]
    return (ACCEPTED if _rel(len(parts), p.get("relation", "exactly"), p["n"]) else REJECTED), \
        f"paragraphs={len(parts)}"


def _norm_num(s: str) -> str | None:
    s = s.replace(",", "")
    try:
        f = float(s)
    except ValueError:
        return None
    return str(int(f)) if f == int(f) else repr(f)


_NUM = re.compile(r"(?<![\w.])\d{1,3}(?:,\d{3})+(?:\.\d+)?|(?<![\w.])\d+(?:\.\d+)?")


def numbers_in(text: str) -> set[str]:
    out = set()
    for m in _NUM.findall(text):
        n = _norm_num(m)
        if n is not None:
            out.add(n)
    return out


def chk_numbers_supported(text, p, spec):
    """回應裡的每一個數字，都要出現在來源裡。**只出 rejected 或 unknown**（誠實邊界 3）。

    `ignore_small`：<= 這個值的整數不檢查（「3 個重點」「第 1 點」這類結構性數字）。
    """
    src = "\n".join(spec.sources.values())
    src_nums = numbers_in(src)
    small = p.get("ignore_small", 10)
    missing = []
    for n in sorted(numbers_in(text)):
        try:
            if float(n) <= small and float(n) == int(float(n)):
                continue
        except ValueError:
            pass
        if n not in src_nums:
            missing.append(n)
    if missing:
        return REJECTED, f"numbers not in source: {missing[:8]}"
    return UNKNOWN, "all numbers found (not evidence of support)"


def _normtext(s: str) -> str:
    s = unicodedata.normalize("NFKC", s).lower()
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", s)).strip()


def ngram_support(text: str, source: str, n: int = 3) -> float | None:
    """回應的 n-gram 有幾成逐字出現在來源裡。回應太短 ⇒ None。"""
    t, s = _normtext(text).split(), _normtext(source).split()
    grams = [tuple(t[i:i + n]) for i in range(len(t) - n + 1)]
    if not grams:
        return None
    sg = {tuple(s[i:i + n]) for i in range(len(s) - n + 1)}
    return sum(1 for g in grams if g in sg) / len(grams)


def chk_extractive(text, p, spec):
    """幾乎逐字取自來源 ⇒ accepted；否則 unknown。**不出 rejected**（改寫不是錯）。"""
    r = ngram_support(text, "\n".join(spec.sources.values()), p.get("n", 3))
    if r is None:
        return UNKNOWN, "too short"
    return (ACCEPTED if r >= p["min_ratio"] else UNKNOWN), f"ngram_support={r:.3f}"


def quote_in(quote: str, text: str) -> bool:
    """評審附的引文是否逐字（正規化空白與標點後）出現在 text 裡。"""
    q = _normtext(quote)
    return bool(q) and q in _normtext(text)


CHECKS: dict[str, Callable] = {
    "word_count": chk_word_count, "regex_count": chk_regex_count,
    "contains_all": chk_contains_all, "forbids": chk_forbids,
    "keyword_freq": chk_keyword_freq, "letter_freq": chk_letter_freq,
    "case": chk_case, "json_parses": chk_json_parses,
    "starts_ends": chk_starts_ends, "paragraphs": chk_paragraphs,
    "numbers_supported": chk_numbers_supported, "extractive": chk_extractive,
}


# ───────────────────────── 評審介面 ─────────────────────────

@dataclass
class JudgeResult:
    """評審後端回來的東西。`verdict` 已經是三值；`tokens` 是這一通的總 token（入＋出）。"""
    verdict: str
    tokens: int
    quote: str | None = None
    raw: str | None = None
    cost_usd: float | None = None


#: 後端簽名：(spec, output_text, [criteria]) -> {criterion_id: JudgeResult}
#: 一次可以問多條（同一題的多條準則合併成一通，省固定開銷）。
JudgeFn = Callable[[Spec, str, list[Criterion]], dict[str, JudgeResult]]


# ───────────────────────── 級聯 ─────────────────────────

def aggregate(verdicts: list[str]) -> str:
    """任一 rejected ⇒ rejected；全部 accepted ⇒ accepted；否則 unknown。"""
    if any(v == REJECTED for v in verdicts):
        return REJECTED
    if verdicts and all(v == ACCEPTED for v in verdicts):
        return ACCEPTED
    return UNKNOWN


def evaluate(spec: Spec, output: str, judge: JudgeFn | None = None, *,
             require_quote: bool = False, short_circuit: bool = True,
             judge_policy: str = "allowlist") -> dict:
    """跑一份規格。回 `{verdict, receipt_class, infra_void, criteria:[…], judge_tokens, …}`。

    `judge_policy`：
      "allowlist"（**產品預設**）——評審的裁決只在 `Criterion.judge_may_decide` 為真時算數；
        其餘降成 unknown，但理由（`evidence`）留著。
      "measure"——評審的裁決一律算數。**只給量測用**（ops/research_20260924 的 V2 用它量
        「如果讓評審決定會怎樣」），不是產品行為。
    `receipt_class`：D＝裁決只來自確定性檢查；J＝有評審的票被算進去；U＝裁決是 unknown。
    `infra_void`：有評審呼叫**失敗**（後端回 `verdict="infra_void"`）。它不是評審的判斷，
      也不是 unknown 的一種說法——呼叫端必須另外數（2026-09-24 用量上限事故）。

    `short_circuit`：確定性層已經 rejected ⇒ 不再花 token（整體已經不可能 accepted）。
    `require_quote`：評審的 rejected／accepted 要附引文，引文逐字核不到 ⇒ unknown。
    """
    if judge_policy not in ("allowlist", "measure"):
        raise ValueError(f"judge_policy {judge_policy!r}")
    infra_void = False
    rows: list[dict] = []
    pending: list[Criterion] = []
    for c in spec.criteria:
        if c.kind == "check":
            v, ev = CHECKS[c.check](output, c.params, spec)
            rows.append({"id": c.id, "layer": "check", "verdict": v, "evidence": ev,
                         "screen": c.screen})
            if v == UNKNOWN and c.fallback_judge:
                pending.append(c)
        else:
            rows.append({"id": c.id, "layer": "judge", "verdict": UNKNOWN,
                         "evidence": "not yet judged"})
            pending.append(c)
    tokens, calls, cost = 0, 0, 0.0
    det_rejected = any(r["verdict"] == REJECTED for r in rows)
    skipped = None
    if pending and (short_circuit and det_rejected):
        skipped = "short_circuit_rejected"
    elif pending and judge is None:
        skipped = "no_judge"
    elif pending and spec.judge_token_cap is not None and (
            estimate_tokens(output + "".join(spec.sources.values())
                            + "".join(c.question or "" for c in pending))
            > spec.judge_token_cap):
        # **呼叫前**就擋：預估會超過上限就不問（0 token），那幾條留在 unknown。
        skipped = "over_token_cap"
        for c in pending:
            next(r for r in rows if r["id"] == c.id).update(
                verdict=UNKNOWN, evidence="over token cap (not asked)")
    elif pending:
        res = judge(spec, output, pending)
        calls = 1
        for c in pending:
            jr = res.get(c.id)
            row = next(r for r in rows if r["id"] == c.id)
            if jr is None:
                row.update(layer="judge", verdict=UNKNOWN, evidence="judge gave no answer")
                continue
            if jr.verdict == "infra_void":
                infra_void = True
                row.update(layer="judge", verdict=UNKNOWN, evidence="judge call failed (infra_void)")
                continue
            v = jr.verdict if jr.verdict in VERDICTS else UNKNOWN
            ev = f"judge:{jr.verdict}"
            if v != UNKNOWN and judge_policy == "allowlist" and not c.judge_may_decide:
                v, ev = UNKNOWN, f"judge:{jr.verdict} (advisory; criterion not allowlisted)"
            if require_quote and v != UNKNOWN:
                pool = output if v == REJECTED else "\n".join(spec.sources.values()) or output
                if not (jr.quote and quote_in(jr.quote, pool)):
                    v, ev = UNKNOWN, f"judge:{jr.verdict} but quote not found verbatim"
            row.update(layer="judge", verdict=v, evidence=ev)
        tokens = sum(r.tokens for r in {id(x): x for x in res.values()}.values()) if res else 0
        cost = sum((r.cost_usd or 0.0) for r in {id(x): x for x in res.values()}.values()) if res else 0.0
    counted = [r for r in rows if not (r.get("screen") and r["verdict"] != REJECTED)]
    verdict = aggregate([r["verdict"] for r in counted])
    if verdict == UNKNOWN:
        rclass = "U"
    elif verdict == REJECTED:
        rclass = "D" if any(r["verdict"] == REJECTED and r["layer"] == "check" for r in counted) else "J"
    else:
        rclass = "J" if any(r["layer"] == "judge" for r in counted) else "D"
    return {"verdict": verdict, "receipt_class": rclass, "infra_void": infra_void,
            "criteria": rows,
            "judge_tokens": tokens, "judge_calls": calls, "judge_cost_usd": cost,
            "judge_skipped": skipped, "spec_sha256": spec.sha256()}


def estimate_tokens(text: str) -> int:
    """粗估 token（約 4 字元／token）——只用來在**呼叫前**決定要不要超預算，
    不拿來報成本（報成本用後端回報的真用量）。"""
    return max(1, len(text) // 4)
