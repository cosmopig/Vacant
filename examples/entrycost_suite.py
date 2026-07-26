#!/usr/bin/env python3
"""入場成本設計的實驗套件（E1–E9，確定性模擬）。

目的：回答「身份的入場成本該怎麼設計」。這是 2026-07-26 獨立審查留下的
唯一結構性設計問題，而它需要實測而不是推理。

每個實驗一個問題、一個掃描軸、多個 seed。所有原始逐輪紀錄都留檔
（runs/<實驗>/<格>.jsonl），摘要另存 summary.json，不覆寫原始檔。

用法：
    python examples/entrycost_suite.py --out 專題/實驗記錄/入場成本_2026-07-26
    python examples/entrycost_suite.py --out DIR --only E1 E6   # 只跑某幾支
    python examples/entrycost_suite.py --out DIR --seeds 5      # 快速版
"""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vacant.entrycost import EntryPolicy, SimConfig, simulate  # noqa: E402

DEFAULT_SEEDS = 20


def _commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True, timeout=10,
                              cwd=Path(__file__).resolve().parent.parent).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "?"


def _cell(out: Path, exp: str, label: str, cfgs: list[SimConfig]) -> dict:
    """跑一格（同一設定 × 多 seed），回傳聚合。逐輪紀錄逐 seed 落檔。"""
    logdir = out / exp / "logs"
    logdir.mkdir(parents=True, exist_ok=True)
    results = []
    for cfg in cfgs:
        safe = label.replace("/", "_").replace(" ", "")
        lp = logdir / f"{safe}__{cfg.seed}.jsonl"
        results.append(simulate(cfg, log_path=lp))

    def agg(key: str) -> dict:
        vals = [r[key] for r in results if r[key] is not None]
        if not vals:
            return {"mean": None, "n": 0}
        return {
            "mean": round(statistics.mean(vals), 4),
            "sd": round(statistics.pstdev(vals), 4) if len(vals) > 1 else 0.0,
            "min": round(min(vals), 4), "max": round(max(vals), 4),
            "n": len(vals),
        }

    return {
        "label": label,
        "n_seeds": len(cfgs),
        "accepted_bad": agg("accepted_bad"),
        "caught": agg("caught"),
        "clean_paid": agg("clean_paid"),
        "identities_used": agg("identities_used"),
        "routed_to_attacker": agg("routed_to_attacker"),
        "bad_per_route": agg("bad_per_route"),
        "roi": agg("roi"),
        "honest_damage": agg("honest_damage"),
        "blocked_no_endorser": agg("blocked_no_endorser"),
        # 攻擊者一次都沒得手的 seed 佔比——比平均值更能說明「守住了沒有」
        "shutout_rate": round(
            sum(1 for r in results if r["accepted_bad"] == 0) / len(results), 3),
        "raw": results,
    }


def _seeds(n: int, tag: str) -> list[str]:
    return [f"{tag}-s{i}" for i in range(n)]


# ── 實驗定義 ──────────────────────────────────────────────────────────
def E1(out: Path, ns: int) -> dict:
    """攻擊者的最佳策略是什麼？（現況：入場免費、p=0.2）"""
    cells = []
    for st in ("whitewash", "patient", "sybil"):
        cells.append(_cell(out, "E1", st, [
            SimConfig(rounds=400, strategy=st, seed=s) for s in _seeds(ns, f"E1{st}")]))
    return {"question": "在現行設計下，三種攻擊姿態哪一種最有利？",
            "axis": "strategy", "cells": cells}


def E2(out: Path, ns: int) -> dict:
    """稽核率如何改變攻擊者的收益？（這是信任層唯一的真值錨）"""
    cells = []
    for p in (0.02, 0.05, 0.1, 0.2, 0.4, 1.0):
        cells.append(_cell(out, "E2", f"p={p}", [
            SimConfig(rounds=400, audit_rate=p, strategy="patient", seed=s)
            for s in _seeds(ns, f"E2p{p}")]))
    return {"question": "稽核抽樣率 p 對攻擊者成功次數的邊際效果？",
            "axis": "audit_rate", "cells": cells}


def E3(out: Path, ns: int) -> dict:
    """見習期 m 是目前唯一的實質入場成本，它值多少？"""
    cells = []
    for m in (0, 1, 2, 3, 5, 8):
        cells.append(_cell(out, "E3", f"m={m}", [
            SimConfig(rounds=400, probation_m=m, audit_rate=0.05,
                      strategy="whitewash", seed=s)
            for s in _seeds(ns, f"E3m{m}")]))
    return {"question": "見習期長度 m 對洗白攻擊的效果？（低稽核率下才看得出來）",
            "axis": "probation_m", "cells": cells}


def E4(out: Path, ns: int) -> dict:
    """路徑一：外生入場成本（先做 N 筆不計酬的乾淨交付）。"""
    cells = []
    for k in (0, 2, 5, 10, 20):
        cells.append(_cell(out, "E4", f"stake={k}", [
            SimConfig(rounds=400, audit_rate=0.05,
                      entry=EntryPolicy("stake", stake_deliveries=k),
                      strategy="whitewash", seed=s)
            for s in _seeds(ns, f"E4k{k}")]))
    return {"question": "外生入場成本要多大才擋得住洗白？",
            "axis": "stake_deliveries", "cells": cells}


def E5(out: Path, ns: int) -> dict:
    """路徑二：背書連坐。連坐強度 λ 越小罰越重。"""
    cells = []
    for lam in (1.0, 0.9, 0.7, 0.5, 0.3):
        cells.append(_cell(out, "E5", f"λ={lam}", [
            SimConfig(rounds=400, audit_rate=0.05,
                      entry=EntryPolicy("endorse", endorse_min_obs=1.0,
                                        endorse_liability=lam),
                      strategy="whitewash", seed=s)
            for s in _seeds(ns, f"E5l{lam}")]))
    return {"question": "背書連坐要多重才有效？代價是誠實居民被連累多少？",
            "axis": "endorse_liability", "cells": cells}


def E6(out: Path, ns: int) -> dict:
    """三種設計的正面對照（同策略、同稽核率、同輪數）。"""
    designs = [
        ("free", EntryPolicy("free")),
        ("stake(5)", EntryPolicy("stake", stake_deliveries=5)),
        ("stake(10)", EntryPolicy("stake", stake_deliveries=10)),
        ("endorse(λ=0.5)", EntryPolicy("endorse", endorse_liability=0.5)),
    ]
    cells = []
    for label, pol in designs:
        cells.append(_cell(out, "E6", label, [
            SimConfig(rounds=400, audit_rate=0.05, entry=pol,
                      strategy="whitewash", seed=s)
            for s in _seeds(ns, f"E6{label}")]))
    return {"question": "三條路直接對照：哪一個在同樣條件下讓攻擊者最不划算？",
            "axis": "entry_policy", "cells": cells}


def E7(out: Path, ns: int) -> dict:
    """耐心攻擊者：熬過見習再作惡。入場成本擋不擋得住這種？"""
    cells = []
    for label, pol in [("free", EntryPolicy("free")),
                       ("stake(10)", EntryPolicy("stake", stake_deliveries=10)),
                       ("endorse(λ=0.5)", EntryPolicy("endorse", endorse_liability=0.5))]:
        cells.append(_cell(out, "E7", label, [
            SimConfig(rounds=400, audit_rate=0.05, entry=pol,
                      strategy="patient", build_rounds=15, seed=s)
            for s in _seeds(ns, f"E7{label}")]))
    return {"question": "入場成本對「耐心型」攻擊者有效嗎？（它本來就打算先付出）",
            "axis": "entry_policy", "cells": cells}


def E8(out: Path, ns: int) -> dict:
    """生態規模：誠實居民越多，攻擊者被路由到的機會越少。"""
    cells = []
    for n in (2, 3, 5, 10, 20):
        cells.append(_cell(out, "E8", f"honest={n}", [
            SimConfig(rounds=400, n_honest=n, audit_rate=0.05,
                      strategy="whitewash", seed=s)
            for s in _seeds(ns, f"E8n{n}")]))
    return {"question": "生態規模本身算不算一種入場成本？",
            "axis": "n_honest", "cells": cells}


def E9(out: Path, ns: int) -> dict:
    """種子穩健性：同一設定重複多次，結論會不會翻盤。"""
    cells = [_cell(out, "E9", "free/whitewash/p=0.05", [
        SimConfig(rounds=400, audit_rate=0.05, strategy="whitewash", seed=s)
        for s in _seeds(max(ns * 2, 40), "E9")])]
    return {"question": "同設定多次重複，結論是否穩定？",
            "axis": "seed", "cells": cells}


def E12(out: Path, ns: int) -> dict:
    """同儕評審的準確率：這是整個模擬最重要的敏感度參數。

    先前所有格子預設 accuracy=0.7。若評審是 oracle（1.0），系統防禦力會被
    嚴重高估——稽核之所以存在，正是因為評審不可信。反過來，評審越差，
    確定性稽核就越是唯一的真值錨。
    """
    cells = []
    for acc in (1.0, 0.7, 0.5, 0.3, 0.0):
        cells.append(_cell(out, "E12", f"acc={acc}", [
            SimConfig(rounds=400, audit_rate=0.05, reviewer_accuracy=acc,
                      strategy="patient", build_rounds=15, seed=s)
            for s in _seeds(ns, f"E12a{acc}")]))
    return {"question": "同儕評審的準確率如何改變攻擊者的收益？"
                        "（評審越不可靠，稽核錨越承重）",
            "axis": "reviewer_accuracy", "cells": cells}


def E13(out: Path, ns: int) -> dict:
    """在**悲觀但真實**的評審假設下，三種入場設計還分得出高下嗎？"""
    cells = []
    for label, pol in [("free", EntryPolicy("free")),
                       ("stake(10)", EntryPolicy("stake", stake_deliveries=10)),
                       ("endorse(λ=0.5)", EntryPolicy("endorse", endorse_liability=0.5))]:
        for acc in (0.7, 0.3):
            cells.append(_cell(out, "E13", f"{label}/acc={acc}", [
                SimConfig(rounds=400, audit_rate=0.05, entry=pol,
                          reviewer_accuracy=acc, strategy="patient",
                          build_rounds=15, seed=s)
                for s in _seeds(ns, f"E13{label}{acc}")]))
    return {"question": "評審不可靠時，入場成本設計還有沒有差別？",
            "axis": "policy×reviewer_accuracy", "cells": cells}


EXPERIMENTS = {"E1": E1, "E2": E2, "E3": E3, "E4": E4, "E5": E5,
               "E6": E6, "E7": E7, "E8": E8, "E9": E9, "E12": E12, "E13": E13}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--seeds", type=int, default=DEFAULT_SEEDS)
    ap.add_argument("--only", nargs="*", default=None)
    args = ap.parse_args()

    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    names = args.only or list(EXPERIMENTS)
    manifest = {
        "suite": "entrycost",
        "commit": _commit(),
        "started_iso": time.strftime("%Y-%m-%d %H:%M:%S"),
        "seeds_per_cell": args.seeds,
        "experiments": names,
        "note": "確定性模擬；路由/稽核/扣分全走真實機制，模擬的只有交付好壞。",
    }
    (out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    all_results = {}
    for name in names:
        t0 = time.time()
        print(f"\n=== {name} ===", flush=True)
        res = EXPERIMENTS[name](out, args.seeds)
        res["elapsed_s"] = round(time.time() - t0, 1)
        all_results[name] = res
        print(f"  {res['question']}")
        for c in res["cells"]:
            ab, roi = c["accepted_bad"], c["roi"]
            print(f"  {c['label']:20s} 成功作惡 {ab['mean']:6.2f}±{ab['sd']:<5.2f} "
                  f"| 全數擋下的 seed {c['shutout_rate']:.0%} "
                  f"| ROI {roi['mean'] if roi['n'] else '—'} "
                  f"| 誠實方損失 {c['honest_damage']['mean']}", flush=True)
        # 逐支落盤，跑一半中斷也留得住已完成的
        (out / f"{name}.json").write_text(
            json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")

    summary = {k: {"question": v["question"], "axis": v["axis"],
                   "cells": [{kk: c[kk] for kk in
                              ("label", "accepted_bad", "roi", "shutout_rate",
                               "honest_damage", "clean_paid", "identities_used")}
                             for c in v["cells"]]}
               for k, v in all_results.items()}
    (out / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n完成。原始逐輪紀錄在 {out}/*/logs/，摘要在 {out}/summary.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
