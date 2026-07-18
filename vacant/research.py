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
from itertools import product
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


# === 統計擴充：Holm / 配對 TOST / Wilcoxon exact / McNemar power（零 scipy）====
def holm_adjust(pvalues: list[float]) -> list[float]:
    """Holm-Bonferroni 逐步下降校正（族錯誤率控制），零 scipy。

    對排序後 p_(1)<=...<=p_(n) 依序算 min(1,(n-i+1)*p_(i))，再取累積最大值
    保證單調不減，最後映回原始順序。空輸入回傳空列表；任一 p 不在 [0,1]
    內即拋 ValueError。
    """
    n = len(pvalues)
    if n == 0:
        return []
    for p in pvalues:
        if not (0.0 <= p <= 1.0):
            raise ValueError("p-values must be in [0,1]")
    order = sorted(range(n), key=lambda i: pvalues[i])
    adjusted = [0.0] * n
    running_max = 0.0
    for rank, idx in enumerate(order):
        factor = n - rank
        val = min(1.0, factor * pvalues[idx])
        running_max = max(running_max, val)
        adjusted[idx] = running_max
    return adjusted


def _binom_upper_tail(k: int, n: int, p: float = 0.5) -> float:
    """P(K >= k)，K ~ Binomial(n, p)；k<=0 回 1.0，k>n 回 0.0。"""
    if k <= 0:
        return 1.0
    if k > n:
        return 0.0
    return sum(math.comb(n, i) * (p ** i) * ((1 - p) ** (n - i)) for i in range(k, n + 1))


def paired_tost(x: list[float], y: list[float], low: float, high: float, *,
                 alpha: float = 0.05) -> dict:
    """配對等效性 TOST（Two One-Sided Tests），符號檢定版、零 scipy、精確二項檢定。

    對差值 d_i = x_i - y_i：
      下側檢定 H0: median(d) <= low  vs  Ha: median(d) > low
        統計量 k_lo = #{d_i > low}（d_i == low 的配對整對剔除），
        p_lower = P(K >= k_lo)，K~Binomial(n_lo, 0.5)。
      上側檢定 H0: median(d) >= high vs  Ha: median(d) < high
        統計量 k_hi = #{d_i < high}（d_i == high 的配對整對剔除），
        p_upper = P(K >= k_hi)，K~Binomial(n_hi, 0.5)。
      p_tost = max(p_lower, p_upper)；p_tost < alpha 判定等效（d 落在 (low, high) 內）。

    邊界情境明確處理：
      - 若某側全部配對都被剔除（n_lo=0 或 n_hi=0），該側 p 設為 1.0（保守，不宣稱等效）。
      - low>=high 或 alpha 不在 (0,1) 或 x/y 長度不一或為空 → ValueError。
    """
    if low >= high:
        raise ValueError("low must be < high")
    if not (0.0 < alpha < 1.0):
        raise ValueError("alpha must be in (0,1)")
    if len(x) != len(y):
        raise ValueError("x and y must have equal length")
    if len(x) == 0:
        raise ValueError("empty input")
    d = [xi - yi for xi, yi in zip(x, y)]

    d_lo = [v for v in d if v != low]
    n_lo = len(d_lo)
    if n_lo == 0:
        p_lo = 1.0
    else:
        k_lo = sum(1 for v in d_lo if v > low)
        p_lo = _binom_upper_tail(k_lo, n_lo, 0.5)

    d_hi = [v for v in d if v != high]
    n_hi = len(d_hi)
    if n_hi == 0:
        p_hi = 1.0
    else:
        k_hi = sum(1 for v in d_hi if v < high)
        p_hi = _binom_upper_tail(k_hi, n_hi, 0.5)

    p_tost = max(p_lo, p_hi)
    return dict(p_lower=p_lo, p_upper=p_hi, p_tost=p_tost,
                equivalent=p_tost < alpha, n=len(d))


def wilcoxon_exact(x: list[float], y: list[float] | None = None) -> dict:
    """配對 Wilcoxon 符號等級精確檢定（零 scipy，2^m 完整枚舉零假設分布）。

    y=None 時 x 視為差值 d；否則逐配對算 d = x-y。
    規則：
      - d_i == 0 的配對整對剔除（zero-drop，Wilcoxon 慣例）。
      - |d_i| 同分用平均等級（midrank）；此設計使「精確」枚舉建立在等級值上，
        與無 tie 時的教科書精確分布一致，屬標準取捨、非隱藏近似。
      - 非零配對數 m==0 → p_two_sided=1.0（無資訊）。
      - m>20 → ValueError（2^m 枚舉爆炸，非本模組適用範圍）。
      - 空輸入或 x/y 長度不一 → ValueError。
    """
    if y is not None:
        if len(x) != len(y):
            raise ValueError("x and y must have equal length")
        d = [xi - yi for xi, yi in zip(x, y)]
    else:
        d = list(x)
    if len(d) == 0:
        raise ValueError("empty input")
    d_nz = [v for v in d if v != 0]
    m = len(d_nz)
    if m == 0:
        return dict(W_plus=0.0, W_minus=0.0, n_nonzero=0, p_two_sided=1.0)
    if m > 20:
        raise ValueError("n_nonzero too large for exact enumeration (>20)")

    abs_d = [abs(v) for v in d_nz]
    order = sorted(range(m), key=lambda i: abs_d[i])
    ranks = [0.0] * m
    i = 0
    while i < m:
        j = i
        while j + 1 < m and abs_d[order[j + 1]] == abs_d[order[i]]:
            j += 1
        avg_rank = (i + 1 + j + 1) / 2.0
        for t in range(i, j + 1):
            ranks[order[t]] = avg_rank
        i = j + 1

    w_plus = sum(r for r, v in zip(ranks, d_nz) if v > 0)
    w_minus = sum(r for r, v in zip(ranks, d_nz) if v < 0)
    total = w_plus + w_minus
    obs_min = min(w_plus, w_minus)

    count_le = 0
    total_patterns = 2 ** m
    for signs in product((1, -1), repeat=m):
        s = sum(r for r, sgn in zip(ranks, signs) if sgn > 0)
        if s <= obs_min + 1e-9:
            count_le += 1
    p = min(1.0, 2.0 * count_le / total_patterns)
    return dict(W_plus=w_plus, W_minus=w_minus, n_nonzero=m, p_two_sided=p)


def _norm_cdf(z: float) -> float:
    """標準常態分布 CDF（用 math.erf，零 scipy）。"""
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def _norm_ppf(p: float) -> float:
    """標準常態分布分位數（Acklam 有理逼近，|誤差|<1.15e-9，零 scipy）。"""
    if not (0.0 < p < 1.0):
        raise ValueError("p must be in (0,1)")
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    p_low = 0.02425
    p_high = 1.0 - p_low
    if p < p_low:
        q = math.sqrt(-2.0 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
               ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0)
    if p <= p_high:
        q = p - 0.5
        r = q * q
        return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / \
               (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1.0)
    q = math.sqrt(-2.0 * math.log(1.0 - p))
    return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
           ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0)


def mcnemar_power(n: int, p_disc: float, delta: float, *, alpha: float = 0.05) -> float:
    """McNemar 檢定的漸近檢定力（常態近似，Connor 1987），零 scipy。

    n：配對樣本數；p_disc=p10+p01（不一致比例）；delta=p10-p01（配對效應）。
      z_beta = (|delta|*sqrt(n) - z_{alpha/2}*sqrt(p_disc)) / sqrt(p_disc - delta^2)
      power  = Phi(z_beta)
    封閉解檢查：delta=0 時 z_beta = -z_{alpha/2}，故 power == alpha/2（與 n、p_disc
    無關），可手算核對。
    """
    if n <= 0:
        raise ValueError("n must be positive")
    if not (0.0 < p_disc <= 1.0):
        raise ValueError("p_disc must be in (0,1]")
    if not (0.0 < alpha < 1.0):
        raise ValueError("alpha must be in (0,1)")
    if abs(delta) >= p_disc:
        raise ValueError("abs(delta) must be < p_disc")
    var_term = p_disc - delta * delta
    z_a = _norm_ppf(1.0 - alpha / 2.0)
    z_beta = (abs(delta) * math.sqrt(n) - z_a * math.sqrt(p_disc)) / math.sqrt(var_term)
    return _norm_cdf(z_beta)


def mcnemar_sample_size(p_disc: float, delta: float, *, alpha: float = 0.05,
                          power: float = 0.8) -> int:
    """達到目標 power 所需最小配對樣本數（Connor 1987 常態近似，向上取整），零 scipy。"""
    if not (0.0 < p_disc <= 1.0):
        raise ValueError("p_disc must be in (0,1]")
    if delta == 0:
        raise ValueError("delta must be nonzero")
    if abs(delta) >= p_disc:
        raise ValueError("abs(delta) must be < p_disc")
    if not (0.0 < alpha < 1.0):
        raise ValueError("alpha must be in (0,1)")
    if not (0.0 < power < 1.0):
        raise ValueError("power must be in (0,1)")
    var_term = p_disc - delta * delta
    z_a = _norm_ppf(1.0 - alpha / 2.0)
    z_b = _norm_ppf(power)
    n = ((z_a * math.sqrt(p_disc) + z_b * math.sqrt(var_term)) / abs(delta)) ** 2
    return math.ceil(n)


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
