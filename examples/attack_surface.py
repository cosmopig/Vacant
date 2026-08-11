"""A1–A3 · B1–B5 · C1–C5：文獻驅動的新攻擊面（2026-08-07）。

## 這一輪要回答什麼

前一輪（E17–E24）把 Srivatsa 2005 的 **model I**（固定週期方波＝我們叫的
`pulse`）掃了個遍，然後在複驗時發現六條結論被推翻三條。這一輪補三個
**別人做過、我們沒測過**的攻擊面。理由不是新穎性——本專案唯一交付物是
實體展覽，不寫論文也不投稿——理由是**不能對觀眾說錯話**：展場說
「這套機制擋得住攻擊」，那就得真的測過。

  A（2.1）Srivatsa model II–IV：指數分佈間隔 / 隨機好度 / 正弦漸變。
          他量到四個模型的攻擊者成本比 1 : 2.28 : 2.08 : 1.36（越低越划算，
          ⇒ model I 最划算）。他的防禦是單一個 PID 式信任模型；我們的是
          見習期＋UCB＋抽樣稽核＋乘法 slash 四道同時跑。**這個比值在我們的
          組態下長什麼樣？**

  B（2.2）評審端攻擊（Hoffman 2009 §4）：ballot-stuffing / slandering / 混合。
          我們測過的攻擊全部在交付端；`registry.py` 對評審端寫了四層防禦，
          **在這一輪之前沒有一層被真的攻擊過**。

  C（2.3）見習期正面對決。外生入場費已被證明無效（E1–E16 ＋ Friedman &
          Resnick 2001）。見習期是還活著的那道防禦，但從沒被正面量過。

## 分析紀律（沿用脈衝那一輪第六節，違反＝結論作廢）

  1. 對聚合量下「維度 X 不重要」的結論前**先分解它**。所以每一格都同時報
     曝光（routed_to_attacker）、效率（bad_per_route）、以及 Srivatsa 的
     成本分解（misuse_x / build_y）——不是只報 accepted_bad。
  2. **不在退化端點上量效應量**。共謀比例不掃到 100%、盲區主軸不放在 1.0。
  3. 偵測機率是單一乘積 (1−盲區)×抽樣率×準確率，三者同軸。
  4. 等預算比較要驗 `defected == BUDGET` 不是 `<=`。

## 誠實邊界

  - 全部是**機制模擬**，不是生態效果。攻擊者與共謀者的劇本是我們寫死的
    （Güneş/Sun 2019 已示範用無導數最佳化自動搜策略，我們沒用）。
  - 逐輪 JSONL 全落盤；聚合前的原始資料一行都沒有被覆蓋。
"""
from __future__ import annotations

import argparse
import json
import statistics as st
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from vacant.collusion import CollusionConfig
from vacant.collusion import simulate as collude_sim
from vacant.entrycost import SimConfig
from vacant.entrycost import simulate as entry_sim
from vacant.registry import ReviewDefenses

ROUNDS = 600
SEEDS = [f"a{i}" for i in range(12)]        # 交付端（entrycost）：12 seeds
C_ROUNDS = 250
C_SEEDS = [f"c{i}" for i in range(10)]      # 評審端（collusion）：10 seeds，較慢

# 這一輪報告要看的欄位。**曝光與效率一定要在**（紀律 1）。
ENTRY_KEYS = ("accepted_bad", "defected", "caught", "routed_to_attacker",
              "clean_paid", "identities_used", "bad_per_route", "roi",
              "srivatsa_cost", "misuse_x", "build_y", "mean_tv", "mean_bh",
              "high_value_hits", "blind_passes", "n_bursts", "hits_per_burst",
              "react_lag_mean", "honest_damage")
COL_KEYS = ("honest_rep_end", "honest_rep_drop", "honest_rep_min",
            "colluder_rep_end", "route_share_colluder", "route_share_ratio",
            "routes_colluder", "routes_honest", "informative_tasks",
            "accepted_bad", "defected", "caught",
            "mean_w_colluder", "mean_w_honest", "mean_w_collusive_vote",
            "n_collusive_votes", "reviews_rejected",
            "reviewer_slash_false_fail", "reviewer_slash_false_pass",
            "reviewer_slash_on_colluder", "reviewer_slash_precision")


def _stat(vals: list) -> dict:
    v = [x for x in vals if x is not None]
    if not v:
        return {"mean": None, "sd": None, "min": None, "max": None, "n": 0}
    return {"mean": round(st.mean(v), 4),
            "sd": round(st.pstdev(v), 4) if len(v) > 1 else 0.0,
            "min": min(v), "max": max(v), "n": len(v)}


def _run_entry(args):
    cfg, log = args
    return entry_sim(cfg, log_path=Path(log) if log else None)


def _run_collude(args):
    cfg, log = args
    return collude_sim(cfg, log_path=Path(log) if log else None)


def _cell(pool, fn, label: str, cfgs: list, logdir: Path | None, keys) -> dict:
    jobs = []
    for cfg in cfgs:
        lp = None
        if logdir is not None:
            logdir.mkdir(parents=True, exist_ok=True)
            safe = label.replace("/", "_").replace("=", "").replace(" ", "")
            lp = str(logdir / f"{safe}__{cfg.seed}.jsonl")
        jobs.append((cfg, lp))
    runs = list(pool.map(fn, jobs))
    out = {"label": label, "n_seeds": len(runs),
           "config_digest": runs[0]["config_digest"]}
    for k in keys:
        out[k] = _stat([r.get(k) for r in runs])
    # 逐 seed 原值：聚合量不足以支撐任何「維度 X 不重要」的結論（紀律 1），
    # 複驗者必須拿得到原始向量才做得了分解與配對檢定。
    out["raw"] = {k: [r.get(k) for r in runs] for k in keys}
    out["shutout_rate"] = round(
        sum(1 for r in runs if r.get("accepted_bad") == 0) / len(runs), 4)
    return out


def _agg(name: str, axis: str, axis_label: str, question: str, note: str,
         cells: list) -> dict:
    return {"name": name, "question": question, "axis": axis,
            "axis_label": axis_label, "note": note, "cells": cells}


def _ld(out: Path | None, name: str) -> Path | None:
    """該實驗的逐輪紀錄目錄；--no-logs 時回 None。"""
    return None if out is None else out / name / "logs"


def _mk(seed: str, **kw) -> SimConfig:
    base = dict(rounds=ROUNDS, seed=seed)
    base.update(kw)
    return SimConfig(**base)


def _ck(seed: str, **kw) -> CollusionConfig:
    base = dict(rounds=C_ROUNDS, seed=seed)
    base.update(kw)
    return CollusionConfig(**base)


# ══ A. Srivatsa model I–IV ═══════════════════════════════════════════
# 四個模型的對照必須在**同一個工作週期**上比，否則比的是「作惡比例」不是
# 「時間結構」（脈衝那一輪 4.5 節就是栽在沒鎖住這個）。Srivatsa 的 Figure 5
# 是好壞各半的方波，model III 的好度 g~U[0,1] 期望值也是 0.5，model IV 的
# sin 平均同樣是 0.5——所以 model I 取 burst=recover 才對得上。
MODELS = (("I·方波", dict(strategy="pulse")),
          ("II·指數間隔", dict(strategy="osc_exp")),
          ("III·隨機好度", dict(strategy="osc_random")),
          ("IV·正弦漸變", dict(strategy="osc_sine")))


def a1(out: Path, pool) -> dict:
    """A1 四模型主對照（週期 10、工作週期 0.5），盲區 0 與 0.5 各一組。"""
    cells = []
    for blind in (0.0, 0.5):
        for lab, kw in MODELS:
            cells.append(_cell(pool, _run_entry, f"{lab} · blind={blind}",
                               [_mk(s, pulse_burst=5, pulse_recover=5,
                                    blindspot=blind, **kw) for s in SEEDS],
                               _ld(out, "A1"), ENTRY_KEYS))
    return _agg("A1", "model × blindspot", "四個震盪模型",
                "Srivatsa 的成本比 1 : 2.28 : 2.08 : 1.36 在我們的組態下長什麼樣？",
                "週期固定 10（burst=recover=5），工作週期 0.5——四個模型的期望"
                "作惡比例因此相同，差的只有時間結構。", cells)


def a2(out: Path, pool) -> dict:
    """A2 週期掃描：攻擊者把節奏調到防禦的記憶長度上會怎樣？

    Srivatsa：知道 maxH 的攻擊者以週期＝maxH 震盪最划算。我們沒有 maxH，
    對應物是 Beta 的 decay 半衰期（200 事件）與 UCB 的觀測累積——**不是同一種
    記憶**，所以這一格是「有沒有類似結構」的探測，不是複製他的結果。
    """
    cells = []
    for period in (4, 10, 40):
        half = period // 2
        for lab, kw in MODELS:
            cells.append(_cell(pool, _run_entry, f"{lab} · P={period}",
                               [_mk(s, pulse_burst=half, pulse_recover=half,
                                    blindspot=0.25, **kw) for s in SEEDS],
                               _ld(out, "A2"), ENTRY_KEYS))
    return _agg("A2", "period × model", "震盪週期",
                "攻擊者把週期調到多少最划算？有沒有「調到防禦記憶長度」這回事？",
                "盲區固定 0.25——刻意避開 0.5（脈衝那一輪量到時間結構效應為零的"
                "交叉點）與 1.0（退化端點，30 seeds 塌成一條軌跡）。", cells)


def a3(out: Path, pool) -> dict:
    """A3 等預算對照：把作惡總量鎖死，只比時機。

    脈衝那一輪的 4.5 節發現「等預算」根本沒綁住（只有 whitewash 用得完），
    新判準改驗 `defected == BUDGET`。這裡用綁得住的小預算重做。
    """
    cells = []
    for budget in (1, 2):
        for lab, kw in MODELS:
            cells.append(_cell(pool, _run_entry, f"{lab} · 預算={budget}",
                               [_mk(s, pulse_burst=5, pulse_recover=5,
                                    blindspot=0.25, defect_budget=budget, **kw)
                                for s in SEEDS],
                               _ld(out, "A3"), ENTRY_KEYS))
    return _agg("A3", "budget × model", "等預算（時機純化）",
                "作惡總量鎖死之後，四個模型的時機差異值多少？",
                "驗收要看 defected 的 mean 是否等於預算——`<=` 是恆成立的上界，"
                "驗不到「預算沒綁住」（脈衝那一輪 4.5 節的教訓）。", cells)


# ══ B. 評審端攻擊 ═════════════════════════════════════════════════════
def b1(out: Path, pool) -> dict:
    """B1 攻擊型態 × 共謀者比例。共謀比例只掃到 3/6（紀律 2）。"""
    cells = []
    for mode in ("none", "stuff", "slander", "mixed"):
        for n_col in (1, 2, 3):
            cells.append(_cell(pool, _run_collude,
                               f"{mode} · {n_col}/{6}",
                               [_ck(s, mode=mode, n_colluders=n_col,
                                    n_honest=6 - n_col, defect_rate=0.5)
                                for s in C_SEEDS],
                               _ld(out, "B1"), COL_KEYS))
    return _agg("B1", "mode × collude_frac", "評審端攻擊型態 × 共謀比例",
                "互抬、抹黑、混合各自能拿到多少？",
                "人口固定 6 人，共謀者 1–3 人（16.7%–50%）。"
                "**刻意不掃到 100%**：全員共謀時「誠實者被壓低」是恆等式不是量測。", cells)


def b2(out: Path, pool) -> dict:
    """B2 四層防禦逐一拆掉。拆掉數字沒變的那一層就是裝飾（blayer 紀律）。"""
    arms = (("全開", ReviewDefenses(), True),
            ("關W·weight內生", ReviewDefenses(endogenous_weight=False), True),
            ("關S·自報同源", ReviewDefenses(same_controller=False), True),
            ("關B·行為同源", ReviewDefenses(behavior_same_source=False), True),
            ("關U·未證明遞減", ReviewDefenses(unproven_decay=False), True),
            # 第五層住在 ecosystem 不住在 registry，所以它不是 ReviewDefenses 的
            # 一格，而是 CollusionConfig 的旗標。它與前四層性質不同：前四層是
            # 「猜這票可不可信」的先驗降權，這一層是「被客觀事實抓到說謊」的後果。
            ("關R·稽核錨評審後果", ReviewDefenses(), False),
            ("全關", ReviewDefenses(False, False, False, False), False))
    cells = []
    for mode in ("slander", "mixed"):
        for lab, d, rs in arms:
            cells.append(_cell(pool, _run_collude, f"{mode} · {lab}",
                               [_ck(s, mode=mode, n_colluders=2, n_honest=4,
                                    defect_rate=0.5, defenses=d,
                                    reviewer_slash=rs)
                                for s in C_SEEDS],
                               _ld(out, "B2"), COL_KEYS))
    return _agg("B2", "defense ablation", "四層防禦逐一拆掉",
                "哪一層真的在承重？哪一層拆掉數字不變？",
                "2 共謀者 / 6 人。每一層單獨關，另加全開與全關兩個端點。", cells)


def b3(out: Path, pool) -> dict:
    """B3 內部人 vs 新身份 × 自報同源 vs 匿名。

    `_reviewer_weight` 的宣稱是「全新 Sybil reviewer obs=0 → weight ≈ 地板」。
    那句話只涵蓋**新身份**。已經站穩的內部人轉為共謀時，這一層在定義上不動它。
    """
    cells = []
    for warm in (True, False):
        for shared in (True, False):
            lab = ("內部人" if warm else "新身份") + ("·自報同源" if shared else "·匿名")
            cells.append(_cell(pool, _run_collude, lab,
                               [_ck(s, mode="mixed", n_colluders=2, n_honest=4,
                                    defect_rate=0.5, colluder_warmup=warm,
                                    shared_controller=shared) for s in C_SEEDS],
                               _ld(out, "B3"), COL_KEYS))
    return _agg("B3", "insider × controller", "內部人／新身份 × 自報／匿名",
                "防禦擋得住的到底是哪一種共謀者？",
                "「自報同源」那一格是給 registry 最好的條件——攻擊者沒有義務"
                "自報 controller，所以匿名那一格才是現實。", cells)


def b4(out: Path, pool) -> dict:
    """B4 共謀強度：每票以 collude_prob 照劇本投，其餘照實。"""
    cells = [_cell(pool, _run_collude, f"抹黑強度={p}",
                   [_ck(s, mode="slander", n_colluders=2, n_honest=4,
                        defect_rate=0.5, collude_prob=p) for s in C_SEEDS],
                   _ld(out, "B4"), COL_KEYS)
             for p in (0.0, 0.25, 0.5, 0.75, 1.0)]
    return _agg("B4", "collude_prob", "共謀強度",
                "要多常動手才有效？低強度共謀是不是反而更划算（更難被行為推斷抓到）？",
                "collude_prob=0 等於對照臂（＝mode none）。", cells)


def b5(out: Path, pool) -> dict:
    """B5 抹黑 → 搶到路由 → 換成實際損害。

    抹黑本身不直接產生壞交付；它的價值是**把路由搶過來**。這一格把那條
    因果鏈的第二段接上：搶到路由之後開始作惡，總得手多多少？
    """
    cells = []
    for mode in ("none", "slander"):
        for dr in (0.0, 0.25, 0.5, 1.0):
            cells.append(_cell(pool, _run_collude, f"{mode} · 作惡率={dr}",
                               [_ck(s, mode=mode, n_colluders=2, n_honest=4,
                                    defect_rate=dr) for s in C_SEEDS],
                               _ld(out, "B5"), COL_KEYS))
    return _agg("B5", "mode × defect_rate", "抹黑的兌現路徑",
                "抹黑搶到的路由，換算成多少壞交付得手？",
                "紀律 1 的應用：得手 = 曝光 × 效率。抹黑動的是曝光那一項，"
                "所以只看得手數會看不出它在做什麼。", cells)


# ══ C. 見習期正面對決 ═════════════════════════════════════════════════
def c1(out: Path, pool) -> dict:
    """C1 見習筆數 probation_m。對手是 whitewash（換身份重來）。"""
    cells = []
    for strat in ("whitewash", "pulse"):
        for m in (0, 2, 4, 8, 16):
            cells.append(_cell(pool, _run_entry, f"{strat} · m={m}",
                               [_mk(s, strategy=strat, probation_m=m,
                                    pulse_burst=5, pulse_recover=5,
                                    blindspot=0.25) for s in SEEDS],
                               _ld(out, "C1"), ENTRY_KEYS))
    return _agg("C1", "probation_m", "見習筆數",
                "見習期拉長，把 whitewash 的成本推高多少？",
                "m=0 等於沒有強制稽核那一段（見習判準仍由 obs 內生，"
                "所以這不等於完全拆掉見習期——拆掉那一格在 C2/C3）。", cells)


def c2(out: Path, pool) -> dict:
    """C2 路由端上限 probation_cap。1.0 ＝拆掉這道蓋子。"""
    cells = []
    for strat in ("whitewash", "pulse"):
        for cap in (0.35, 0.55, 0.75, 1.0):
            cells.append(_cell(pool, _run_entry, f"{strat} · cap={cap}",
                               [_mk(s, strategy=strat, probation_cap=cap,
                                    pulse_burst=5, pulse_recover=5,
                                    blindspot=0.25) for s in SEEDS],
                               _ld(out, "C2"), ENTRY_KEYS))
    return _agg("C2", "probation_cap", "見習生的 UCB 上限",
                "0.55 這個數字承重嗎？拆掉（cap=1.0）數字會變嗎？",
                "0.55 目前是手調常數，沒有推導依據——這一格就是在問它值不值得留。", cells)


def c3(out: Path, pool) -> dict:
    """C3 見習配額 probation_every。設很大等於拆掉配額。"""
    cells = []
    for strat in ("whitewash", "pulse"):
        for every in (2, 10, 10**6):
            cells.append(_cell(pool, _run_entry,
                               f"{strat} · every={'∞' if every > 10**5 else every}",
                               [_mk(s, strategy=strat, probation_every=every,
                                    pulse_burst=5, pulse_recover=5,
                                    blindspot=0.25) for s in SEEDS],
                               _ld(out, "C3"), ENTRY_KEYS))
    return _agg("C3", "probation_every", "見習配額",
                "每幾筆路由留一個見習名額？配額同時是防禦的洞（給攻擊者定期送單）"
                "與冷啟動的命脈（讓 m 筆強制稽核真的發生）。",
                "every=∞ 等於永久流放：新人永遠選不到，強制稽核永遠不發生。", cells)


def c4(out: Path, pool) -> dict:
    """C4 身份重造成本：見習期在身份多便宜時開始失效？"""
    cells = [_cell(pool, _run_entry, f"whitewash · 身份成本={c}",
                   [_mk(s, strategy="whitewash", identity_cost=c,
                        blindspot=0.25) for s in SEEDS],
                   _ld(out, "C4"), ENTRY_KEYS)
             for c in (0.0, 1.0, 2.0, 4.0, 8.0, 16.0)]
    return _agg("C4", "identity_cost", "身份重造成本",
                "身份要多貴，見習期才守得住？",
                "身份成本是**外生**參數，不是機制產物——這一格量的是「若身份有價，"
                "見習期的 ROI 曲線長什麼樣」，不是「我們有辦法讓身份變貴」。"
                "Friedman & Resnick 2001 已證明入場費只是把一種無效率換成另一種。", cells)


def c5(out: Path, pool) -> dict:
    """C5 並行身份數：攻擊者同時養 N 個身份，見習配額就被它多佔 N 份。"""
    cells = []
    for strat in ("whitewash", "sybil"):
        for n in (1, 2, 4, 8):
            cells.append(_cell(pool, _run_entry, f"{strat} · 並行={n}",
                               [_mk(s, strategy=strat, n_attackers=n,
                                    blindspot=0.25) for s in SEEDS],
                               _ld(out, "C5"), ENTRY_KEYS))
    return _agg("C5", "n_attackers", "並行身份數",
                "攻擊者有幾個並行身份時，見習期就擋不住了？",
                "見習配額是「每 10 筆路由留一個名額給見習生」——名額由所有見習生"
                "競爭，攻擊者多養一個身份就多搶一份。", cells)


EXPS = {"A1": a1, "A2": a2, "A3": a3,
        "B1": b1, "B2": b2, "B3": b3, "B4": b4, "B5": b5,
        "C1": c1, "C2": c2, "C3": c3, "C4": c4, "C5": c5}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--only", nargs="*", default=None)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--no-logs", action="store_true",
                    help="不落逐輪紀錄（只在快速探索時用；正式跑一定要留）")
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)

    names = a.only or list(EXPS)
    sp = a.out / "summary.json"
    summary = json.loads(sp.read_text()) if sp.exists() else {}

    with ProcessPoolExecutor(max_workers=a.workers) as pool:
        for name in names:
            t0 = time.time()
            print(f"── {name} ──", flush=True)
            res = EXPS[name](a.out if not a.no_logs else None, pool)
            res["elapsed_s"] = round(time.time() - t0, 1)
            (a.out / f"{name}.json").write_text(
                json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
            summary[name] = {"question": res["question"], "axis": res["axis"],
                             "elapsed_s": res["elapsed_s"],
                             "cells": [c["label"] for c in res["cells"]]}
            for c in res["cells"]:
                head = f"   {c['label']:<24}"
                if "route_share_ratio" in c:
                    print(f"{head} 誠實信譽 {c['honest_rep_end']['mean']:>7}"
                          f"  共謀信譽 {c['colluder_rep_end']['mean']:>7}"
                          f"  路由倍率 {c['route_share_ratio']['mean']:>6}"
                          f"  得手 {c['accepted_bad']['mean']:>6}", flush=True)
                else:
                    print(f"{head} 得手 {c['accepted_bad']['mean']:>6}"
                          f"  曝光 {c['routed_to_attacker']['mean']:>6}"
                          f"  效率 {c['bad_per_route']['mean']}"
                          f"  cost {c['srivatsa_cost']['mean']}"
                          f"  (X {c['misuse_x']['mean']} / Y {c['build_y']['mean']})",
                          flush=True)
            print(f"   （{res['elapsed_s']}s）", flush=True)
            sp.write_text(json.dumps(summary, ensure_ascii=False, indent=1),
                          encoding="utf-8")

    (a.out / "manifest.json").write_text(json.dumps({
        "generated": time.strftime("%Y-%m-%d %H:%M"),
        "entry_rounds": ROUNDS, "entry_seeds": SEEDS,
        "collusion_rounds": C_ROUNDS, "collusion_seeds": C_SEEDS,
        "note": "文獻驅動的新攻擊面：A＝Srivatsa 2005 model II–IV，"
                "B＝Hoffman 2009 §4 的評審端攻擊，C＝見習期正面對決。"
                "全部是機制模擬，不是生態效果。",
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n寫出 {a.out}")


if __name__ == "__main__":
    main()
