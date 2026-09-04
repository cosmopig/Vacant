#!/usr/bin/env python3
"""R446／EQ5 的**事前**檢定力投影 ＋ power_paired 的課本值自檢（round697）。

為什麼要這一支：
  DECISION_20260904_R446_EQUAL_BUDGET_ARM.md §六-2 承諾「n_d<15 ⇒ 寫 UNRESOLVED
  並**同時**報 MDE／N₈₀」，但那兩個數字**沒有寫在任何地方**。analyze_eq5.py 算的
  MDE 是**從觀測到的 discordant rate 回推**的——那是事後量。round678 §六 的鐵律是
  「UNRESOLVED 要分『沒量出來』與『沒有差異』，收官寫 CI 的同時必須寫**事前**投影」，
  事後算的 MDE 答不了「這個設計本來就量不到」這個問題。

  本檔在 r446 的 rows 落地之前跑完並 commit。輸入只有 DECISION 寫死的設計常數
  （n=371、alpha=0.05、PRACTICAL_PP=5.0），**不讀 runs/**——這是它能當事前量的唯一理由。

  順帶補上 round678 的另一條鐵律：「自己現寫的統計小工具要先對課本值自檢」。
  paired_ci.diff_ci 在 round656 已雙向驗證，但 power_paired 的 exact_mcnemar_p／
  mde_at_n／n_needed_for_power 從來沒有對過課本值——而 §六-2 指名要用它們。

新增可調參數：**0**。alpha 沿用 paired_ci.ALPHA、實務門檻沿用 paired_ci.PRACTICAL_PP、
n 取自 DECISION 的 --n 371。
"""
from __future__ import annotations
import argparse, json, math, pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from ops.gain.replay.paired_ci import diff_ci, verdict, PRACTICAL_PP, ALPHA  # noqa: E402
from ops.gain.power_paired import exact_mcnemar_p, mde_at_n, n_needed_for_power  # noqa: E402

# DECISION §三 寫死的設計常數。改這裡＝改事前註冊 ⇒ 不准。
N_PLANNED = 371
# void 會把 measured 壓低；DECISION §四 P-R446-8 的窗是 void<=5% ⇒ 敏感度掃這個範圍。
N_GRID = [N_PLANNED, round(N_PLANNED * 0.95), round(N_PLANNED * 0.90)]


# ---------------------------------------------------------------- 課本值自檢
# round697：檢查一律**注入** p 函式，不使用 import 進來的名字。
# 理由是實測：`from ops.gain.power_paired import exact_mcnemar_p` 綁的是本模組的
# 區域名字，改 `pp.exact_mcnemar_p` 對它無效（記憶鐵律「突變體寫在模組層永遠不生效」）。
# 最初版本的 F 就踩了這個坑：突變後 A/C 用的還是原函式 ⇒ 那條偵測線沒有牙齒。
def _checks(pfun, mde) -> list[str]:
    """全部判準集中在這裡，乾淨跑與突變跑走**同一份**程式碼。"""
    fails = []

    # A：精確 McNemar ＝ 雙尾符號檢定，p = 2 * P(X<=min(b,c))，X~Bin(b+c, 0.5)
    for b, c, want in [(6, 0, 2 / 64), (5, 0, 2 / 32), (10, 0, 2 / 1024),
                       (8, 1, 2 * 10 / 512), (1, 1, 1.0), (0, 0, 1.0)]:
        got = pfun(b, c)
        if abs(got - min(1.0, want)) > 1e-12:
            fails.append(f"A: p({b},{c}) = {got!r}, 課本值 {min(1.0, want)!r}")

    # B：對稱性 p(b,c) == p(c,b)
    bad = [(b, c) for b in range(12) for c in range(12)
           if abs(pfun(b, c) - pfun(c, b)) > 1e-15]
    if bad:
        fails.append(f"B: 不對稱 {len(bad)} 格，例：{bad[:3]}")

    # C：全同向時達到顯著的最小 n_d ＝ 6（2*0.5^6=0.03125<0.05；n_d=5 是 0.0625）
    sig = [n for n in range(1, 12) if pfun(n, 0) < 0.05]
    if not sig or sig[0] != 6:
        fails.append(f"C: 全同向最小顯著 n_d 應為 6，得 {sig[:1]}")

    # D：兩把尺同刻度——mde_at_n 用 McNemar p<0.05，收官的仲裁者是 diff_ci 的區間位置。
    #    paired_ci 宣稱兩者在「排除 0」等價；這裡對 mde 指名的 split 逐格驗，不引用宣稱。
    for n in N_GRID:
        for rate in (0.02, 0.05, 0.10, 0.20, 0.35):
            m = mde(n, rate)
            if m["min_gap"] is None:
                continue
            b, c = m["min_split"]
            r = diff_ci(b, c, n)
            if not r["lo"] > 0:
                fails.append(f"D: n={n} rate={rate} split={b},{c} 宣稱顯著但 "
                             f"diff_ci 沒排除 0 (lo={r['lo'] * 100:.3f}pp)")
            if abs(m["mde_pp"] - 100.0 * (b - c) / n) > 1e-9:
                fails.append(f"D: n={n} rate={rate} mde_pp 與 split 不一致")
            if b - c >= 2 and diff_ci(b - 1, c + 1, n)["lo"] > 0:
                fails.append(f"D: n={n} rate={rate} 小一格仍顯著 ⇒ mde 不是最小值")

    # E：n_needed_for_power 的課本行為（不吃 pfun，突變時原樣通過＝正常）
    if n_needed_for_power(0.5) != -1:
        fails.append("E: p_b=0.5（無效果）應回 -1")
    seq = [n_needed_for_power(p) for p in (0.55, 0.60, 0.70, 0.80)]
    if seq != sorted(seq, reverse=True):
        fails.append(f"E: 效果越大需要的配對數應單調變少，得 {seq}")
    if not 30 <= n_needed_for_power(0.70) <= 80:
        fails.append(f"E: n_needed_for_power(0.70)={n_needed_for_power(0.70)} 離課本量級太遠")
    return fails


def selftest(verbose: bool = True) -> int:
    fails = list(_checks(exact_mcnemar_p, mde_at_n))

    # F：植入缺陷。突變在**被測函式內部**生效（改 power_paired 模組的名字），
    #    然後把 _checks 整套重跑一次——要求它至少叫一條。這條驗的是「偵測器有牙齒」，
    #    判準不是 rc≠0，是指名「_checks 回傳的條數必須 > 0」。
    import ops.gain.power_paired as pp
    orig = pp.exact_mcnemar_p
    mutants = {
        # M1 單尾（漏乘 2）⇒ n_d=5 就會"顯著"，A 與 C 都該叫
        "M1_one_tailed": lambda b, c: orig(b, c) / 2,
        # M2 忽略平手方向（拿 max 不是 min）⇒ 對稱性與課本值都該叫
        "M2_use_max": lambda b, c: min(1.0, 2 * sum(
            __import__("math").comb(b + c, i) for i in range(max(b, c) + 1)) / (2 ** (b + c)))
        if b + c else 1.0,
    }
    for name, fn in mutants.items():
        try:
            pp.exact_mcnemar_p = fn
            caught = _checks(fn, pp.mde_at_n)
            if not caught:
                fails.append(f"F: 突變體 {name} 沒有被任何判準看見 ⇒ 偵測器沒牙齒")
        finally:
            pp.exact_mcnemar_p = orig
    # 突變還原後乾淨跑必須仍然乾淨（證明 F 沒有留下汙染）
    if _checks(exact_mcnemar_p, mde_at_n):
        fails.append("F: 突變還原後乾淨跑不再乾淨 ⇒ 自檢有副作用")

    if verbose:
        for f in fails:
            print("FAIL " + f)
        print(f"selftest: {'PASS' if not fails else 'FAIL'}（{len(fails)} 條）")
    return 1 if fails else 0


# ---------------------------------------------------------------- 事前投影
def reach(n: int, nd: int) -> dict:
    """在 measured=n、discordant=nd 之下，兩個極端情形各會落到四格表的哪一格。

    best  = 全部同向（b=nd, c=0）：這個 nd 能拿到的最強證據。
    tie   = 對半（b=c）：真的打平時會落到哪一格——**這才是「打平說不說得出口」**。
    """
    def cell(b, c):
        r = diff_ci(b, c, n)
        lo, hi = r["lo"] * 100, r["hi"] * 100
        return {"lo_pp": round(lo, 3), "hi_pp": round(hi, 3),
                "delta_pp": round(r["delta"] * 100, 3), "verdict": verdict(lo, hi)}
    return {"n": n, "n_d": nd, "best": cell(nd, 0), "tie": cell(nd // 2, nd - nd // 2)}


def project(n: int) -> dict:
    # 1) 能排除 0 的最小 n_d（全同向）
    min_nd_signal = next((nd for nd in range(1, 400) if reach(n, nd)["best"]["verdict"] == "ON_WINS"), None)
    # 2) 打平仍算「有結論」（RULED_OUT）的最大 n_d：hi_pp 隨 sqrt(n_d) 成長 ⇒ 有上界。
    #    ⚠ 只掃**偶數** n_d：奇數的 b=nd//2, c=b+1 根本不是打平（delta 微負），
    #    它會把 hi 壓到 +5 以下而以單邊的理由拿到 RULED_OUT。round697 第一版沒排除
    #    奇數，量出 91；那是奇偶假象，真正的邊界是 82（偶數、b=c 的最大值）。
    tie_ok = [nd for nd in range(2, 400, 2) if reach(n, nd)["tie"]["verdict"] == "RULED_OUT"]
    max_nd_tie = max(tie_ok) if tie_ok else None
    assert tie_ok == list(range(2, max_nd_tie + 1, 2)), "打平窗不連續，邊界說法不成立"
    # 3) MDE：在若干 discordant rate 下，n 題能偵測到的最小效果
    mdes = {}
    for rate in (0.02, 0.05, 0.10, 0.15, 0.20, 0.30):
        m = mde_at_n(n, rate)
        mdes[f"{rate:.2f}"] = {"n_d_expected": m["n_disc_expected"],
                               "mde_pp": None if m["mde_pp"] is None else round(m["mde_pp"], 3)}
    # 4) N₈₀：真實偏向 p_b 時要多少 discordant pair 才有 80% power
    n80 = {f"{p:.2f}": n_needed_for_power(p) for p in (0.60, 0.65, 0.70, 0.75, 0.80)}
    return {"n_measured": n, "min_n_d_for_signal": min_nd_signal,
            "max_n_d_for_informative_tie": max_nd_tie,
            "mde_by_disc_rate": mdes, "n_d_needed_for_80pct_power": n80}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--json")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if selftest():
        print("BROKEN：自檢沒過，不輸出投影（壞尺上不量東西）")
        return 1
    out = {"design_constants": {"n_planned": N_PLANNED, "alpha": ALPHA,
                                "practical_pp": PRACTICAL_PP, "n_grid": N_GRID},
           "reads_runs_dir": False,
           "projection": {str(n): project(n) for n in N_GRID},
           "p_r446_7_threshold_check": {}}
    # P-R446-7 事前寫的是 n_d>=15，理由「低於此則區間必然容得下 ±5pp」——逐格驗這個理由
    for n in N_GRID:
        rows = []
        for nd in range(2, 31):
            r = reach(n, nd)
            rows.append({"n_d": nd, "best_verdict": r["best"]["verdict"],
                         "best_lo_pp": r["best"]["lo_pp"], "best_hi_pp": r["best"]["hi_pp"],
                         "best_hi_ge_5pp": r["best"]["hi_pp"] >= PRACTICAL_PP})
        out["p_r446_7_threshold_check"][str(n)] = rows
    js = json.dumps(out, ensure_ascii=False, indent=2)
    if a.json:
        pathlib.Path(a.json).write_text(js, encoding="utf-8")
    print(js)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
