"""Track A 四臂等算力實驗 harness —— 驗證 H0（責任制度造成成品達成需求）。

對應《實驗規格_Vacant假說嚴謹驗證_2026-06-27.md》§3/§4/§7/§12。

四臂（同題配對、同一顆腦、可檢查任務；V = 形式化的「需求」）：
  plain1  = Composer.plain()      單次，無驗證、無責任             —— 基準
  plainK  = Composer.naive(K)     K 次多數決，純算力               —— 加「算力」
  bok_v   = Composer.best_of_n(K) K 次取過 V 的第一個，驗證選擇、無回饋 —— 加「需求驗證」
  vacant  = Composer.vacant(K)    verify-fix，驗證 + 回饋 + 究責    —— 加「責任修補」

把總提升 Acc(vacant)−Acc(plain1) 拆三段並檢定「責任貢獻 > 算力貢獻」(H0)：
  G_算力 = Acc(plainK) − Acc(plain1)
  G_驗證 = Acc(bok_v)  − Acc(plainK)
  G_責任 = Acc(vacant) − Acc(bok_v)
  責任貢獻 = G_驗證 + G_責任

統計：McNemar 精確檢定（配對二元）+ bootstrap CI，零 scipy 相依。
誠實邊界：只在「有客觀 V」的任務成立；V≠GT 以抓 Goodhart（§5.3）。

離線自驗：`python -m vacant.research`（確定性 stub，純測管線/統計，**非證據**）。
真模型：`python -m vacant.research --suite code --model <name> --base http://host:1234`。
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Callable

from .composer import Composer

Verifier = Callable[[str], bool]
ARMS = ("plain1", "plainK", "bok_v", "vacant")
ARM_LABEL = {
    "plain1": "Plain×1（基準）",
    "plainK": "Plain×K（+算力）",
    "bok_v": "BoK+V（+需求驗證）",
    "vacant": "Vacant×K（+責任修補）",
}


# === 任務 ===================================================================
@dataclass
class Task:
    name: str
    prompt: str
    verify: Verifier            # V_train：迴圈/篩選用（= 形式化需求）
    gt: Verifier               # GT_holdout：評分用（理想上與 verify 不同測資）
    meta: dict = field(default_factory=dict)


@dataclass
class ItemResult:
    task: str
    arm: str
    answer: str
    calls: int
    passed_v: bool
    passed_gt: bool
    asserted: bool             # 系統是否「宣稱達成需求」（plain 永遠宣稱；有 V 的臂只在過 V 時宣稱）


# === 執行 ===================================================================
def _run_arm(arm: str, gen: Callable[[str], str], v: Verifier, k: int):
    c = Composer(gen, v)
    if arm == "plain1":
        return c.plain()
    if arm == "plainK":
        return c.naive(k)
    if arm == "bok_v":
        return c.best_of_n(k)
    if arm == "vacant":
        return c.vacant(k)
    raise ValueError(arm)


def run_item(task: Task, brain_generate: Callable[[str], str], k: int) -> dict[str, ItemResult]:
    """同題跑四臂（配對）。brain_generate(text)->str 是裸腦；本函式負責拼 prompt+feedback。"""
    out: dict[str, ItemResult] = {}
    for arm in ARMS:
        gen = lambda fb, _bp=task.prompt: brain_generate(_bp + fb)
        r = _run_arm(arm, gen, task.verify, k)
        passed_v = task.verify(r.answer)
        passed_gt = task.gt(r.answer)
        asserted = True if arm in ("plain1", "plainK") else passed_v
        out[arm] = ItemResult(task.name, arm, r.answer, r.calls, passed_v, passed_gt, asserted)
    return out


def run_suite(tasks: list[Task], brain_generate: Callable[[str], str], k: int) -> list[dict[str, ItemResult]]:
    return [run_item(t, brain_generate, k) for t in tasks]


# === 指標（附錄 A）==========================================================
def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _acc(sample: list[dict[str, ItemResult]], arm: str) -> float:
    return _mean([1.0 if r[arm].passed_gt else 0.0 for r in sample])


def metrics(results: list[dict[str, ItemResult]]) -> dict[str, dict]:
    n = len(results)
    m: dict[str, dict] = {}
    for arm in ARMS:
        items = [r[arm] for r in results]
        asserted = [it for it in items if it.asserted]
        m[arm] = dict(
            n=n,
            M1_acc=_mean([1.0 if it.passed_gt else 0.0 for it in items]),
            M2_vprec=(_mean([1.0 if it.passed_gt else 0.0 for it in asserted]) if asserted else float("nan")),
            M3_cov=(len(asserted) / n if n else 0.0),
            M4_confwrong=_mean([1.0 if (it.asserted and not it.passed_gt) else 0.0 for it in items]),
            M5_calls=_mean([float(it.calls) for it in items]),
        )
    return m


def decompose(m: dict[str, dict]) -> dict[str, float]:
    g_compute = m["plainK"]["M1_acc"] - m["plain1"]["M1_acc"]
    g_verify = m["bok_v"]["M1_acc"] - m["plainK"]["M1_acc"]
    g_resp = m["vacant"]["M1_acc"] - m["bok_v"]["M1_acc"]
    return dict(
        G_compute=g_compute, G_verify=g_verify, G_resp=g_resp,
        responsibility=g_verify + g_resp,
        total=m["vacant"]["M1_acc"] - m["plain1"]["M1_acc"],
    )


def discordance(results, arm_a="plain1", arm_b="vacant") -> tuple[int, int, int]:
    """回 (b, c, both_wrong)：b=a錯b對(可復原)、c=a對b錯(回歸)、both_wrong=都錯。"""
    b = sum(1 for r in results if (not r[arm_a].passed_gt) and r[arm_b].passed_gt)
    c = sum(1 for r in results if r[arm_a].passed_gt and (not r[arm_b].passed_gt))
    bw = sum(1 for r in results if (not r[arm_a].passed_gt) and (not r[arm_b].passed_gt))
    return b, c, bw


# === 統計（§7，零 scipy）====================================================
def mcnemar_exact(b: int, c: int) -> float:
    """配對二元的 McNemar 精確（雙尾）：對不一致對 b vs c 做 p=0.5 的二項檢定。"""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) * (0.5 ** n)
    return min(1.0, 2.0 * tail)


def boot_ci(results, stat: Callable[[list], float], *, n_boot=2000, seed=0,
            lo=2.5, hi=97.5) -> tuple[float, float]:
    """對 items 做 bootstrap（重抽配對紀錄），回 stat 的百分位 CI。"""
    rng = random.Random(seed)
    n = len(results)
    if n == 0:
        return float("nan"), float("nan")
    vals: list[float] = []
    for _ in range(n_boot):
        sample = [results[rng.randrange(n)] for _ in range(n)]
        vals.append(stat(sample))
    vals.sort()

    def pct(p: float) -> float:
        i = min(len(vals) - 1, max(0, int(round(p / 100.0 * (len(vals) - 1)))))
        return vals[i]

    return pct(lo), pct(hi)


def _vprec(sample, arm) -> float:
    asserted = [r[arm] for r in sample if r[arm].asserted]
    return _mean([1.0 if it.passed_gt else 0.0 for it in asserted]) if asserted else 0.0


# === 報表 ===================================================================
def render_report(tasks: list[Task], brain_generate: Callable[[str], str], *,
                  k: int = 3, seed: int = 0, title: str = "") -> str:
    results = run_suite(tasks, brain_generate, k)
    m = metrics(results)
    dec = decompose(m)
    b, c, bw = discordance(results, "plain1", "vacant")
    p_h1 = mcnemar_exact(b, c)

    d_lo, d_hi = boot_ci(results, lambda s: _acc(s, "vacant") - _acc(s, "plain1"), seed=seed)
    # 責任貢獻 − 算力貢獻 = Acc(vacant)+Acc(plain1) − 2·Acc(plainK)
    rc_lo, rc_hi = boot_ci(results, lambda s: _acc(s, "vacant") + _acc(s, "plain1") - 2 * _acc(s, "plainK"), seed=seed)
    gr_lo, gr_hi = boot_ci(results, lambda s: _acc(s, "vacant") - _acc(s, "bok_v"), seed=seed)
    h3_lo, h3_hi = boot_ci(results, lambda s: _vprec(s, "vacant") - _acc(s, "plain1"), seed=seed)

    n = len(results)
    L: list[str] = []
    P = L.append
    P("=" * 70)
    P(f"Track A 四臂等算力實驗{('：' + title) if title else ''}  (n={n}, K={k})")
    P("=" * 70)
    P("")
    P(f"  {'臂':<22}{'M1準確':>8}{'M2精確':>8}{'M3涵蓋':>8}{'M4自信錯':>9}{'M5呼叫':>8}")
    for arm in ARMS:
        a = m[arm]
        vprec = "  n/a " if a["M2_vprec"] != a["M2_vprec"] else f"{a['M2_vprec']:>7.0%}"
        P(f"  {ARM_LABEL[arm]:<20}{a['M1_acc']:>8.0%}{vprec:>8}{a['M3_cov']:>8.0%}{a['M4_confwrong']:>9.0%}{a['M5_calls']:>8.2f}")
    P("")
    P("【H0 因果拆解】把總提升掛到哪一步")
    P(f"  G_算力 (plainK−plain1) = {dec['G_compute']:+.0%}")
    P(f"  G_驗證 (bok_v−plainK)  = {dec['G_verify']:+.0%}")
    P(f"  G_責任 (vacant−bok_v)  = {dec['G_resp']:+.0%}")
    P(f"  ─ 責任貢獻 (G_驗證+G_責任) = {dec['responsibility']:+.0%}   vs   算力貢獻 = {dec['G_compute']:+.0%}")
    P(f"  ─ 總提升 (vacant−plain1)   = {dec['total']:+.0%}")
    P(f"  責任−算力 95%CI = [{rc_lo:+.0%}, {rc_hi:+.0%}]   → H0 主檢定（CI下界>0 ⇒ 成功是責任造成）")
    P("")
    P("【H1 增益=可復原錯誤】plain1 vs vacant 配對")
    P(f"  可復原 b={b}  回歸 c={c}  都錯={bw}   Δ={(b - c) / n:+.0%}  95%CI=[{d_lo:+.0%},{d_hi:+.0%}]")
    P(f"  McNemar 精確 p={p_h1:.2e}   (go: Δ CI下界>0 且 c 極小)")
    P("")
    P("【H2 回饋>盲重抽】G_責任 = vacant−bok_v")
    P(f"  G_責任={dec['G_resp']:+.0%}  95%CI=[{gr_lo:+.0%},{gr_hi:+.0%}]   (go: CI下界>0)")
    P("")
    P("【H3 誠實究責】verified-precision(vacant) − accuracy(plain1)")
    P(f"  M2(vacant)={m['vacant']['M2_vprec']:.0%}  −  M1(plain1)={m['plain1']['M1_acc']:.0%}  "
      f"=  {m['vacant']['M2_vprec'] - m['plain1']['M1_acc']:+.0%}  95%CI=[{h3_lo:+.0%},{h3_hi:+.0%}]")
    P(f"  自信錯誤率：plain1={m['plain1']['M4_confwrong']:.0%} → vacant={m['vacant']['M4_confwrong']:.0%}  "
      f"(責任層讓你知道哪題不可信)")
    P("")
    P("註：此為單 run、單 seed 的點估；正式須跨模型×領域×≥3 seeds（規格 §6/§7）。")
    return "\n".join(L)


# === 離線 stub（確定性，純 smoke test；非證據）==============================
def _equals(correct: str) -> Verifier:
    return lambda a, _c=correct: a.strip() == _c


class StubBrain:
    """確定性離線腦：依任務難度類別 + 是否帶『WRONG』修補回饋決定回正解 / 錯解。
    用途僅為離線把整條管線與統計算對；產生的數字**刻意設計、不可當實證**。
      easy          : 永遠對              → 四臂皆過（基準）
      resample      : 任何重抽就對        → bok_v / vacant 過（測 G_驗證）
      recoverable   : 只有 WRONG 回饋才對 → 只有 vacant 過（測 G_責任）
      unrecoverable : 永遠錯              → 四臂皆敗
    """

    name = "stub:deterministic"

    def __init__(self, answers: dict[str, tuple[str, str]]):
        self._ans = answers  # base_prompt -> (class, correct)

    def generate(self, text: str) -> str:
        for bp, (cls, correct) in self._ans.items():
            if text.startswith(bp):
                fb = text[len(bp):]
                if cls == "easy":
                    return correct
                if cls == "unrecoverable":
                    return correct + "_X"
                if cls == "resample":
                    return correct if fb.strip() else correct + "_X"
                if cls == "recoverable":
                    return correct if "WRONG" in fb else correct + "_X"
        return "??"


def synthetic_suite(per_class: int = 10) -> tuple[StubBrain, list[Task]]:
    answers: dict[str, tuple[str, str]] = {}
    tasks: list[Task] = []
    for cls in ("easy", "resample", "recoverable", "unrecoverable"):
        for j in range(per_class):
            name = f"{cls}_{j}"
            bp = f"[TASK {name}] produce the required answer. "
            correct = f"ANS::{name}"
            answers[bp] = (cls, correct)
            v = _equals(correct)
            tasks.append(Task(name, bp, v, v, {"class": cls}))
    return StubBrain(answers), tasks


def code_suite(n: int = 12) -> list[Task]:
    """真模型用：codebench 的 code-gen 任務。
    注意：codebench 單一測資 → 此處 V_train = GT_holdout（共用）；
    要分離 holdout 須換 HumanEval/MBPP（隱藏測試），見規格 §5.3/§13。"""
    from .codebench import code_cases
    tasks: list[Task] = []
    for i, (prompt, verifier) in enumerate(code_cases(n)):
        tasks.append(Task(f"code_{i}", prompt, verifier, verifier, {"holdout": "shared(codebench)"}))
    return tasks


def _main(argv=None) -> None:  # pragma: no cover
    import argparse
    ap = argparse.ArgumentParser(description="Track A 四臂等算力實驗 harness（H0 因果拆解）")
    ap.add_argument("--suite", default="synthetic", choices=["synthetic", "code"])
    ap.add_argument("--k", type=int, default=3)
    ap.add_argument("--n", type=int, default=12, help="code suite 題數")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--model", default=None)
    ap.add_argument("--base", default="http://localhost:1234")
    ap.add_argument("--api", default="responses", choices=["responses", "openai"])
    a = ap.parse_args(argv)

    if a.suite == "synthetic":
        brain, tasks = synthetic_suite()
        print(render_report(tasks, brain.generate, k=a.k, seed=a.seed,
                            title="synthetic stub（離線管線自驗，非證據）"))
    else:
        if not a.model:
            ap.error("--suite code 需要 --model")
        from .brains import LMStudioBrain
        from .codebench import code_system_prompt
        brain = LMStudioBrain(a.base, a.model, api=a.api, max_tokens=512, system=code_system_prompt())
        tasks = code_suite(a.n)
        print(render_report(tasks, brain.generate, k=a.k, seed=a.seed, title=f"code · {brain.name}"))


if __name__ == "__main__":  # pragma: no cover
    _main()
