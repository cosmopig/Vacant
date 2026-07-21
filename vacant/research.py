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


# === 預註冊統計四函式（17 §P0-6／G7；16 號 wp5 規格）============================
# 硬約束：零 scipy（runtime 依賴只有 cryptography 的鐵律不破）——全部純 Python
# 精確／枚舉／bootstrap 實作。X1 主檢定（H-A1/H-A2，Holm 家族）與 X3 的 H2
# 等效檢定（TOST）都從這裡出數字；每函式在 tests/test_research.py 有 ≥3 個
# 手算對照測試（對照值寫進測試註解）。

def holm_bonferroni(pvals: list[float]) -> list[float]:
    """Holm–Bonferroni step-down 調整後 p 值（回傳順序與輸入相同）。

    家族內 m 個假設：最小 p 乘 m、次小乘 m−1…，並對序列取累積最大值保單調。
    X1 的 H-A1＋H-A2 與消融屬同一家族（19 號圖 L5：McNemar p<.05，Holm）。
    """
    m = len(pvals)
    if m == 0:
        return []
    for p in pvals:
        if not 0.0 <= p <= 1.0:
            raise ValueError(f"p 值必須在 [0,1]：{p}")
    order = sorted(range(m), key=lambda i: (pvals[i], i))
    adjusted_sorted: list[float] = []
    running = 0.0
    for rank, i in enumerate(order):
        adj = min(1.0, (m - rank) * pvals[i])
        running = max(running, adj)
        adjusted_sorted.append(running)
    out = [0.0] * m
    for rank, i in enumerate(order):
        out[i] = adjusted_sorted[rank]
    return out


def tost_equiv_boot(
    diffs: list[float],
    delta: float,
    *,
    alpha: float = 0.05,
    n_boot: int = 2000,
    seed: int = 0,
) -> dict[str, float | bool]:
    """配對 TOST 等效檢定（bootstrap 版）：X3 H2「p=1.0 時兩臂無差」的檢定。

    對配對差 diffs 的均值建 (1−2α) bootstrap 百分位 CI（TOST 與 CI 的標準
    對應：兩個單邊 α 檢定 ≡ 一條 (1−2α) CI）。CI 整條落進 [−δ, +δ] → 等效成立。
    誠實邊界：bootstrap CI 在小樣本偏窄，n<20 時結論保守解讀；δ 是預註冊的
    最小在乎效應（X3 H2 的 5pp），不是事後挑的。
    """
    if delta <= 0:
        raise ValueError(f"等效界 δ 必須為正：{delta}")
    n = len(diffs)
    if n == 0:
        raise ValueError("diffs 不可為空（無配對差無法檢定）")
    rng = random.Random(seed)
    vals: list[float] = []
    for _ in range(n_boot):
        vals.append(_mean([diffs[rng.randrange(n)] for _ in range(n)]))
    vals.sort()

    def pct(p: float) -> float:
        i = min(len(vals) - 1, max(0, int(round(p / 100.0 * (len(vals) - 1)))))
        return vals[i]

    lo, hi = pct(100 * alpha), pct(100 * (1.0 - alpha))
    return {
        "mean": _mean(diffs), "ci_lo": lo, "ci_hi": hi, "delta": delta,
        "equivalent": bool(lo >= -delta and hi <= delta),
    }


def wilcoxon_signed_rank_exact(diffs: list[float], *, alpha: float = 0.05) -> dict[str, float]:
    """Wilcoxon signed-rank 精確檢定（雙尾）：配對差是否系統性偏離 0。

    去零 → 對 |diff| 排 midrank（ties 取平均秩）→ W+＝正差秩和。n≤24 時
    2^n 全枚舉精確 p；n>24 用帶 ties 變異數修正的常態近似（精確枚舉 2^25
    以上不值得，近似誤差 O(1/n²)，誠實標明 method 欄）。
    """
    pairs = [abs(d) for d in diffs if d != 0]
    signs = [1 if d > 0 else -1 for d in diffs if d != 0]
    n = len(pairs)
    if n == 0:
        raise ValueError("全部配對差為 0：無秩可排（H0 無法被拒絕）")
    # midrank：同 |d| 群平分秩次（1..n）
    order = sorted(range(n), key=lambda i: pairs[i])
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and pairs[order[j + 1]] == pairs[order[i]]:
            j += 1
        mid = (i + j) / 2.0 + 1.0
        for t in range(i, j + 1):
            ranks[order[t]] = mid
        i = j + 1
    w_plus = sum(r for r, s in zip(ranks, signs) if s > 0)
    total = sum(ranks)  # = n(n+1)/2（ties 平分後總和不變）
    mean_w = total / 2.0

    if n <= 24:
        # 全枚舉 2^n 個符號指派（以值帶重複的秩為單位）
        counts: dict[float, int] = {}

        def rec(k: int, acc: float) -> None:
            if k == n:
                counts[acc] = counts.get(acc, 0) + 1
                return
            rec(k + 1, acc + ranks[k])
            rec(k + 1, acc)

        rec(0, 0.0)
        dev = abs(w_plus - mean_w)
        extreme = sum(c for w, c in counts.items() if abs(w - mean_w) >= dev - 1e-12)
        p = extreme / (2 ** n)
        method = "exact"
    else:
        # 常態近似：Var = (Σ r² − Σ(t³−t)/12 修正) —— ties 修正項
        var = sum(r * r for r in ranks) / 4.0
        tie_sizes: dict[float, int] = {}
        for v in pairs:
            tie_sizes[v] = tie_sizes.get(v, 0) + 1
        tie_corr = sum(t ** 3 - t for t in tie_sizes.values() if t > 1) / 48.0
        var -= tie_corr
        z = (abs(w_plus - mean_w) - 0.5) / math.sqrt(var)  # 連續性修正
        p = 2.0 * (1.0 - _norm_cdf(z))
        method = "normal_approx"
    return {"w_plus": w_plus, "n": float(n), "p": p, "method": method, "alpha": alpha,
            "reject": bool(p < alpha)}


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _binom_pmf(n: int, k: int, p: float) -> float:
    if k < 0 or k > n:
        return 0.0
    if p <= 0.0:
        return 1.0 if k == 0 else 0.0
    if p >= 1.0:
        return 1.0 if k == n else 0.0
    # log 域計算，n 到數千仍穩
    return math.exp(
        math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)
        + k * math.log(p) + (n - k) * math.log(1.0 - p)
    )


def _mcnemar_reject_region(k: int, alpha: float) -> tuple[int, int]:
    """k 個不一致對時，McNemar 精確雙尾 α 的拒絕域：b ≤ lo 或 b ≥ hi（b+c=k）。"""
    if k == 0:
        return (1, -1)  # 空拒絕域
    lo = -1
    for b in range(0, k // 2 + 1):
        tail = sum(_binom_pmf(k, i, 0.5) for i in range(0, b + 1))
        if 2.0 * min(1.0, tail) <= alpha:
            lo = b
        else:
            break
    if lo < 0:
        return (1, -1)
    return (lo, k - lo)


def mcnemar_power(n: int, p_disc: float, psi: float, *, alpha: float = 0.05) -> float:
    """McNemar 精確檢定的檢定力（17 §P1-3 的 ψ 估計 → T 的依據）。

    模型：n 對配對中 K~Binomial(n, p_disc) 個不一致對；每個不一致對以機率
    ψ 落在 b 方向（M2 對 M0 錯），B~Binomial(K, ψ)。檢定力＝精確雙尾 α
    檢定拒絕 H0 的總機率（對 K 與 B 全枚舉加權，無近似）。
    ψ=0.5 時回傳檢定的 size（≤α，精確檢定保守）——可用作自我對帳。
    """
    if n < 0:
        raise ValueError(f"n 必須非負：{n}")
    if not 0.0 <= p_disc <= 1.0 or not 0.0 <= psi <= 1.0:
        raise ValueError("p_disc 與 ψ 必須在 [0,1]")
    power = 0.0
    for k in range(0, n + 1):
        pk = _binom_pmf(n, k, p_disc)
        if pk == 0.0:
            continue
        lo, hi = _mcnemar_reject_region(k, alpha)
        if lo > hi:
            continue
        p_rej = sum(_binom_pmf(k, b, psi) for b in range(0, lo + 1))
        p_rej += sum(_binom_pmf(k, b, psi) for b in range(hi, k + 1))
        power += pk * p_rej
    return power


def mcnemar_n_required(
    p_disc: float,
    psi: float,
    *,
    alpha: float = 0.05,
    power: float = 0.85,
    n_max: int = 20000,
) -> int:
    """達到目標檢定力的最小 n（線性掃描；pilot 後 ψ 餵這裡決定 T，17 §P1-3）。"""
    if not 0.0 < power <= 1.0:
        raise ValueError(f"目標 power 必須在 (0,1]：{power}")
    if psi == 0.5:
        raise ValueError("ψ=0.5 是 H0：任何 n 都達不到目標 power")
    for n in range(1, n_max + 1):
        if mcnemar_power(n, p_disc, psi, alpha=alpha) >= power:
            return n
    raise ValueError(f"n≤{n_max} 內達不到 power={power}（p_disc={p_disc}, ψ={psi}）")


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
