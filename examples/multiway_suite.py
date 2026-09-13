"""M1–M5：單向管線 vs 多向環境（2026-08-07）。

## 這一輪要回答什麼

主持人 2026-08-07：「環境是最重要的，不應只是單一單向資訊輸出入，應該是多方面的
隨時介入。」設計寫在 `專題/Vacant_展望_2026-08-06/06_多向環境架構.md`，
本套件是它的證據。

  M1  殘餘相關性的分解（核心）：把「共同盲區」拆成模型家族造成的與架構造成的
  M1b 架構參數的敏感度：cascade_p / authority_w 沒有外部錨定，必須當參數掃
  M2  總交付品質：add-one-in 階梯，一次只加一條通道
  M3  人類介入的邊際效益：末端稽核 vs 中途介入，等預算（各一次）
  M4  拒絕原語的博弈：只挑簡單任務的 agent，calibration 維擋不擋得住
  M5  求助通道的串供：諮詢過的人來評審同一件

## 分析紀律（違反＝結論作廢）

  ① 對聚合量下結論前先分解：M1 一定要有 β=0 那一列，否則無法宣稱量到的是
     架構造成的還是模型造成的。
  ② 不要在退化端點上量效應量：單向臂的邊際漏看率高到接近 1，那裡逐對 phi
     被壓縮——所以主指標是 `co_blind_excess`（觀測 − 同邊際率下的獨立預測），
     phi 只作附錄，且**跨臂不可直接比**。
  ③ 偵測機率是單一乘積 (1−β)×抽樣率×準確率，三者同軸：通道分離**改不動 β**，
     它改的是評審之間的相關結構。不要把兩件事講成一件。
  ④ 等預算比較要驗 `interventions_fired == budget` 不是 `<=`：M3 的旗標臂
     可能一次都沒開火（面板從不分歧），那本身就是結論，但不能拿來比。

## 誠實邊界

機制模擬，不是生態效果。cascade_p、authority_w、reviewer_accuracy 三個參數
都沒有外部錨定——M1b 掃它們，正文只報「在這個操作點上」。
"""
from __future__ import annotations

import argparse
import json
import time
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool
from pathlib import Path

from vacant.multiway import MWConfig, mean_sd, simulate_mw

ROUNDS = 300
SEEDS = [f"w{i}" for i in range(24)]


def _run_one(args: tuple[MWConfig, str | None]) -> dict:
    cfg, lp = args
    return simulate_mw(cfg, log_path=Path(lp) if lp else None)


def _cell(label: str, base: dict, logdir: Path | None, pool) -> dict:
    """一格＝同一組參數的所有 seed。回聚合＋pool 過的計數。"""
    jobs = []
    for s in SEEDS:
        cfg = MWConfig(rounds=ROUNDS, seed=s, **base)
        lp = None
        if logdir is not None:
            logdir.mkdir(parents=True, exist_ok=True)
            safe = label.replace("/", "_").replace(" ", "").replace("=", "")
            lp = str(logdir / f"{safe}__{s}.jsonl")
        jobs.append((cfg, lp))
    runs = list(pool.map(_run_one, jobs))

    def col(k):
        return [r[k] for r in runs]

    # ── pool 計數再算比率（不是平均各 seed 的比率）──────────────────────
    bad_n = sum(col("bad_reviewed"))
    votes_n = sum(col("total_votes"))
    miss_rate = (sum(col("miss_votes")) / votes_n) if votes_n else None
    all_miss = (sum(col("all_miss_n")) / bad_n) if bad_n else None
    cfg0 = runs[0]["config"]
    k = cfg0["panel_k"]
    beta, acc = cfg0["blindspot"], cfg0["reviewer_accuracy"]
    # ── 基準線的選擇是這一格最重要的方法論決定 ────────────────────────
    # `all_miss − miss_rate^k`（經驗邊際版）在 miss_rate→1 時**機械性地趨近 0**，
    # 而單向臂正是靠權威把 miss_rate 推到 0.8 以上——於是最糟的架構會量出最小的
    # 「超額」。那是退化端點的假象（紀律②）。
    # 改用**理論基準**：K 位獨立評審、同樣的 β 與同樣的準確率，共同放行的機率是
    #     β + (1−β)·(1−acc)^K
    # 這個量只由兩個外生參數決定，**架構動不了它**。觀測減去它就是架構造成的
    # 共同盲區，而且在通道全部關掉時它應該回到 0（模擬的自我檢核）。
    theory = beta + (1 - beta) * (1 - acc) ** k
    arch_excess = (all_miss - theory) if all_miss is not None else None
    indep_emp = miss_rate ** k if miss_rate is not None else None
    excess_emp = (all_miss - indep_emp) if (all_miss is not None) else None
    se = ((all_miss * (1 - all_miss) / bad_n) ** 0.5) if bad_n else None

    return {
        "label": label,
        "n_seeds": len(runs),
        "pooled": {
            "bad_reviewed": bad_n,
            "reviewer_miss_rate": round(miss_rate, 4) if miss_rate is not None else None,
            # 主指標①：操作型共同盲區＝全體評審一起放行的比例
            "all_miss_rate": round(all_miss, 4) if all_miss is not None else None,
            # 主指標②：模型家族的地板（β 與準確率決定，架構動不了）
            "theory_indep_beta": round(theory, 4),
            # 主指標③：觀測 − 地板 ＝ **架構造成的共同盲區**
            "arch_excess": round(arch_excess, 4) if arch_excess is not None else None,
            "arch_share": (round(arch_excess / all_miss, 4)
                           if all_miss else None),
            "all_miss_se": round(se, 4) if se is not None else None,
            # 附錄：經驗邊際版的超額。**端點壓縮，不可跨臂直接比**，留著只為了
            # 讓別人能複核我們沒有挑指標。
            "indep_pred_emp": round(indep_emp, 4) if indep_emp is not None else None,
            "co_blind_excess_emp": round(excess_emp, 4) if excess_emp is not None else None,
        },
        "quality": mean_sd(col("quality")),
        "accepted_bad": mean_sd(col("accepted_bad")),
        "accepted_good": mean_sd(col("accepted_good")),
        "accepted_total": mean_sd(col("accepted_total")),
        "rejected_good": mean_sd(col("rejected_good")),
        "unassigned": mean_sd(col("unassigned")),
        "declines": mean_sd(col("declines")),
        "consults": mean_sd(col("consults")),
        "dispersed": mean_sd(col("dispersed")),
        "caught": mean_sd(col("caught")),
        "defected": mean_sd(col("defected")),
        "interventions_fired": mean_sd(col("interventions_fired")),
        "fire_round": mean_sd([r["fire_round"] for r in runs]),
        "accepted_bad_after_T": mean_sd(col("accepted_bad_after_T")),
        "reviewer_corr_phi": mean_sd(col("reviewer_corr")),
        "config_digest": runs[0]["config_digest"],
        "_runs": runs,     # 給 M3/M4 做逐 seed 對照；寫檔前會被剝掉
    }


def _ld(out: Path | None, name: str) -> Path | None:
    """--no-logs 時不落盤（只在快速探索用；正式跑一定要留，鐵律 3）。"""
    return None if out is None else out / name / "logs"


def _strip(cells: list[dict]) -> list[dict]:
    for c in cells:
        c.pop("_runs", None)
    return cells


# ── M1 殘餘相關性的分解 ────────────────────────────────────────────────
ONEWAY = dict(seal_reviews=False, hide_reputation=False)
SEALED = dict(seal_reviews=True, hide_reputation=False)
HIDDEN = dict(seal_reviews=False, hide_reputation=True)
BOTH = dict(seal_reviews=True, hide_reputation=True)


def m1(out: Path, pool) -> dict:
    cells = []
    for beta in (0.0, 0.3, 0.6):
        for name, kw in (("單向（瀑布＋權威）", ONEWAY), ("＋密封", SEALED),
                         ("＋隱藏信譽", HIDDEN), ("兩者都關（多向）", BOTH)):
            cells.append(_cell(f"β={beta} · {name}", dict(blindspot=beta, **kw),
                               _ld(out, "M1"), pool))
    return {
        "question": "共同盲區裡有多少是架構自己造出來的？",
        "axis": "blindspot × 通道開關",
        "note": "β=0 那一列是關鍵：那裡沒有模型家族的共同盲區，所有超額都是架構造成的。"
                "主指標是 co_blind_excess，不是 phi（見模組 docstring 紀律②）。",
        "cells": _strip(cells),
    }


def m1b(out: Path, pool) -> dict:
    """架構參數的敏感度。這兩個數字沒有外部錨定，不能當事實用。"""
    cells = []
    for cp, aw in ((0.0, 0.0), (0.4, 0.3), (0.8, 0.6), (1.0, 0.9)):
        cells.append(_cell(f"cascade={cp} · authority={aw}",
                           dict(blindspot=0.3, cascade_p=cp, authority_w=aw, **ONEWAY),
                           _ld(out, "M1b"), pool))
    return {
        "question": "架構造成的超額對 cascade_p / authority_w 有多敏感？",
        "axis": "cascade_p × authority_w",
        "note": "(0,0) 是單向架構但把兩條汙染通道的強度設為零——它應該與"
                "『多向』在數值上重合。不重合就代表模擬裡還有沒被指認的相關來源。",
        "cells": _strip(cells),
    }


# ── M2 總交付品質（add-one-in）────────────────────────────────────────
LADDER = [
    ("0 單向管線（現況）", dict()),
    ("1 ＋密封評審", dict(seal_reviews=True)),
    ("2 ＋隱藏信譽", dict(seal_reviews=True, hide_reputation=True)),
    ("3 ＋拒絕原語", dict(seal_reviews=True, hide_reputation=True,
                          declination=True, decliner="honest")),
    ("4 ＋求助通道（多向全開）", dict(seal_reviews=True, hide_reputation=True,
                                      declination=True, decliner="honest",
                                      consult=True, consult_disqualifies=True)),
]


def m2(out: Path, pool) -> dict:
    cells = [_cell(lab, dict(blindspot=0.3, **kw), _ld(out, "M2"), pool)
             for lab, kw in LADDER]
    return {
        "question": "四條通道一次加一條，交付品質怎麼變？",
        "axis": "add-one-in",
        "note": "一次只加一條，否則量到的是四件事的合計，無法歸因（紀律①）。"
                "要同時看 quality（接受的東西裡有多少是好的）、rejected_good（誤攔）"
                "與 unassigned（拒絕造成的覆蓋率損失）——只報 quality 是報好處不報成本。",
        "cells": _strip(cells),
    }


# ── M3 人類介入的邊際效益 ──────────────────────────────────────────────
def m3(out: Path, pool) -> dict:
    cells, raw = [], {}
    for arch, akw in (("單向", ONEWAY), ("多向", BOTH)):
        for human in ("none", "terminal_random", "terminal_flag", "midcourse_flag"):
            lab = f"{arch} · {human}"
            c = _cell(lab, dict(blindspot=0.3, human=human, human_round=100,
                                human_budget=1, **akw), _ld(out, "M3"), pool)
            raw[lab] = c["_runs"]
            cells.append(c)
    # 逐 seed 對照：同一個 seed 下，介入臂與 none 臂的差。介入前的動態完全相同，
    # 所以差就是介入造成的（含後續路由改變的漣漪）。
    ripple = {}
    for arch in ("單向", "多向"):
        base = raw[f"{arch} · none"]
        for human in ("terminal_random", "terminal_flag", "midcourse_flag"):
            arm = raw[f"{arch} · {human}"]
            fired = [r["interventions_fired"] for r in arm]
            pairs = [(b, a) for b, a in zip(base, arm) if a["interventions_fired"] == 1]
            d_bad = [b["accepted_bad"] - a["accepted_bad"] for b, a in pairs]
            d_route = [_route_diff(b["route_line"], a["route_line"], a["fire_round"])
                       for b, a in pairs]
            ripple[f"{arch} · {human}"] = {
                # 等預算的硬檢查：**必須恰好等於 1**，不是 <=1
                "fired_eq_budget": sum(1 for f in fired if f == 1),
                "fired_zero": sum(1 for f in fired if f == 0),
                "n_used": len(pairs),
                "fire_round": mean_sd([a["fire_round"] for _b, a in pairs]),
                "delta_accepted_bad": mean_sd(d_bad),
                "routes_changed_after_fire": mean_sd(d_route),
            }
    return {
        "question": "一次中途介入 vs 一次末端稽核，何者改變更多後續結果？",
        "axis": "架構 × 介入方式",
        "note": "等預算＝各臂恰好一次介入。旗標臂在面板從不分歧時會開火 0 次——"
                "那是結論不是資料缺失，但那些 seed 不可拿來比（紀律④）。"
                "terminal_random（無選擇資訊）與 terminal_flag（有選擇資訊、事後）"
                "的差＝選擇的價值；terminal_flag 與 midcourse_flag 的差＝時機的價值。",
        "ripple": ripple,
        "cells": _strip(cells),
    }


def _route_diff(a: str, b: str, fire: int | None) -> int:
    """介入之後有幾輪的派工對象改變了——展場第 3 拍那句話的字面量。"""
    if fire is None:
        return 0
    return sum(1 for i in range(fire + 1, min(len(a), len(b))) if a[i] != b[i])


# ── M4 拒絕原語的博弈 ──────────────────────────────────────────────────
def m4(out: Path, pool) -> dict:
    cells = []
    for mode in ("none", "honest", "cherrypick"):
        c = _cell(f"decliner={mode}",
                  dict(blindspot=0.3, declination=(mode != "none"),
                       decliner=mode, **BOTH), _ld(out, "M4"), pool)
        # h0 是被換成挑食者的那一位（decliner=cherrypick 時）
        agents = {}
        for a in ("h0", "h1", "h2"):
            agents[a] = {
                "calib_naive": mean_sd([r["per_agent"][a]["calib_naive"] for r in c["_runs"]]),
                "calib_J": mean_sd([r["per_agent"][a]["calib_J"] for r in c["_runs"]]),
                "coverage": mean_sd([r["per_agent"][a]["coverage"] for r in c["_runs"]]),
                "rep": mean_sd([r["per_agent"][a]["rep"] for r in c["_runs"]]),
                "routed": mean_sd([r["per_agent"][a]["routed"] for r in c["_runs"]]),
                "delivered": mean_sd([r["per_agent"][a]["delivered"] for r in c["_runs"]]),
            }
        c["agents"] = agents
        cells.append(c)
    return {
        "question": "拒絕原語會不會被用來只挑簡單任務？calibration 維擋得住嗎？",
        "axis": "decliner 行為",
        "note": "要同時看三個量：calib_naive（規格書的計分法）、calib_J（Youden's J，"
                "判別力版）、coverage（接受率）。若挑食者在前兩個都不難看，"
                "就代表 calibration 維**不是**擋這個博弈的機制，要另找。"
                "系統面看 accepted_good 與 unassigned：個體帳漂亮而系統變差是典型的博弈形狀。",
        "cells": _strip(cells),
    }


# ── M5 求助通道的串供 ──────────────────────────────────────────────────
def m5(out: Path, pool) -> dict:
    specs = [("求助關閉", dict(consult=False)),
             ("求助開 ＋ 取消評審資格", dict(consult=True, consult_disqualifies=True)),
             ("求助開 ＋ 不取消（串供敞開）", dict(consult=True, consult_disqualifies=False))]
    cells = [_cell(lab, dict(blindspot=0.3, declination=True, decliner="honest",
                             **BOTH, **kw), _ld(out, "M5"), pool)
             for lab, kw in specs]
    return {
        "question": "agent 間求助會不會退化成串供？取消評審資格擋得住嗎？代價是什麼？",
        "axis": "consult × 取消評審資格",
        "note": "串供不需要惡意：看過草稿的人再去評審同一件，判斷本來就不獨立。"
                "取消資格是**結構性**的擋法（不靠事後統計偵測相關性，"
                "因此不會誤傷只是評審順序較後的誠實 agent），代價是可用評審變少。",
        "cells": _strip(cells),
    }


EXPS = {"M1": m1, "M1b": m1b, "M2": m2, "M3": m3, "M4": m4, "M5": m5}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--only", nargs="*", default=None)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--no-logs", action="store_true")
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)

    summary = {}
    sp = a.out / "summary.json"
    if sp.exists():
        summary = json.loads(sp.read_text())

    for name in (a.only or list(EXPS)):
        t0 = time.time()
        print(f"── {name} ──", flush=True)
        # **每一支開一個新 pool**：worker 偶發被系統砍掉時（BrokenProcessPool）
        # 只會弄壞當下這一支，已經寫出的 M* 不受影響，重跑也只要補那一支。
        # 第一版共用一個 pool，M2 掛掉就把後面四支全部帶走。
        for attempt in range(3):
            try:
                with ProcessPoolExecutor(max_workers=a.workers) as pool:
                    res = EXPS[name](a.out if not a.no_logs else None, pool)
                break
            except BrokenProcessPool as e:
                print(f"   pool 掛了（第 {attempt + 1} 次）：{e}；重試", flush=True)
        else:
            print(f"   {name} 三次都失敗，跳過", flush=True)
            continue
        res["elapsed_s"] = round(time.time() - t0, 1)
        res["rounds"] = ROUNDS
        res["n_seeds"] = len(SEEDS)
        (a.out / f"{name}.json").write_text(
            json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
        summary[name] = {"question": res["question"], "axis": res["axis"],
                         "elapsed_s": res["elapsed_s"],
                         "cells": [c["label"] for c in res["cells"]]}
        for c in res["cells"]:
            p = c["pooled"]
            print(f"   {c['label']:<32} 共盲 {str(p['all_miss_rate']):>6}"
                  f"±{p['all_miss_se']}  地板 {p['theory_indep_beta']:>6}"
                  f"  架構 {str(p['arch_excess']):>7}"
                  f"  品質 {c['quality']['mean']}"
                  f"  漏 {c['accepted_bad']['mean']}"
                  f"  誤攔 {c['rejected_good']['mean']}"
                  f"  無人接 {c['unassigned']['mean']}", flush=True)
        print(f"   （{res['elapsed_s']}s）", flush=True)

    sp.write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    (a.out / "manifest.json").write_text(json.dumps({
        "generated": time.strftime("%Y-%m-%d %H:%M"),
        "rounds": ROUNDS, "seeds": SEEDS,
        "design": "專題/Vacant_展望_2026-08-06/06_多向環境架構.md",
        "note": "機制模擬，不是生態效果。cascade_p / authority_w / reviewer_accuracy "
                "三個參數沒有外部錨定，結論只在標明的操作點上成立。",
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n寫出 {a.out}")


if __name__ == "__main__":
    main()
