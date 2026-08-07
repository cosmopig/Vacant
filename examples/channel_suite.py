#!/usr/bin/env python3
"""通道分離兩格的掃描 runner（3.1 專長 profile、3.2 commit-reveal 評審）。

    python examples/channel_suite.py --out 專題/實驗記錄/通道分離_2026-08-07

產物（全部落盤，鐵律 3）：
    spec/<標籤>/rows.jsonl    每一輪的原始紀錄（3.1）
    seal/<標籤>/rows.jsonl    每一輪的原始紀錄（3.2）
    spec_cells.jsonl          每一格的摘要（一行一格）
    seal_cells.jsonl          同上
    summary.json              跨 seed 聚合 ＋ 判準判定

判準（寫死在 `_verdicts`，不是事後看數字挑的）：
  3.1 ①分族路由的專家命中率 > 不分族臂，且 > 隨機基準
      ②總交付品質不變差（分族臂 ≥ 不分族臂）
      ③虛無對照（無真專長）不得出現品質增益——否則量到的是「換了個參數」
  3.2 ①密封臂的殘餘（互不相干評審之間的）一致率 < 未密封臂
      ②密封臂對 herd 參數不敏感（瀑布由建構關閉，不是由假設關閉）
      ③兩邊都照實報：若殘餘沒下降，那表示相關性真的來自同源

原始紀錄只寫每格第一個 seed（rows.jsonl 是給人看軌跡用的，不是聚合來源）；
聚合一律讀 *_cells.jsonl。
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vacant.channels import (  # noqa: E402
    SealConfig, SpecConfig, simulate_seal, simulate_specialty,
)

SEEDS = ("c1", "c2", "c3", "c4", "c5")

# 3.1 的格：(標籤, specialists, reviewer_accuracy)。每格跑 profile off/on 兩臂。
SPEC_CELLS = (
    ("main",        True,  0.90),
    ("null",        False, 0.90),   # 虛無對照：沒有真專長
    ("rev070",      True,  0.70),   # 敏感度：評審更不可靠
    ("rev100",      True,  1.00),   # **退化端點**：評語＝環境真值，僅供對照
)

# 3.2 的格：(標籤, n_clones, herd)。每格跑 open/sealed 兩臂。
SEAL_CELLS = (
    ("clone0_herd00", 0, 0.0),   # 無同源、無瀑布：兩臂應完全一致（健全性檢查）
    ("clone0_herd06", 0, 0.6),   # **無同源**：任何相關性都只能是架構造成的
    ("clone0_herd09", 0, 0.9),
    ("clone2_herd00", 2, 0.0),   # 有同源、無瀑布
    ("clone2_herd06", 2, 0.6),   # 兩者都有：這是現實的樣子
    ("clone2_herd09", 2, 0.9),
    ("clone2_herd10", 2, 1.0),   # **退化端點**：全票一致，鑑別題歸零
)


def _agg(rows: list[dict], key: str) -> dict[str, float | None]:
    vals = [r[key] for r in rows if r.get(key) is not None]
    if not vals:
        return {"mean": None, "sd": None, "n": 0}
    return {
        "mean": round(statistics.fmean(vals), 4),
        "sd": round(statistics.stdev(vals), 4) if len(vals) > 1 else 0.0,
        "min": round(min(vals), 4), "max": round(max(vals), 4), "n": len(vals),
    }


def run_spec(out: Path, rounds: int) -> list[dict]:
    cells = []
    for label, specialists, acc in SPEC_CELLS:
        for profile_on in (False, True):
            arm = "profile_on" if profile_on else "profile_off"
            per_seed = []
            for i, seed in enumerate(SEEDS):
                cfg = SpecConfig(rounds=rounds, profile_on=profile_on,
                                 specialists=specialists, reviewer_accuracy=acc, seed=seed)
                log = None
                if i == 0:
                    log = out / "spec" / f"{label}_{arm}" / "rows.jsonl"
                    log.parent.mkdir(parents=True, exist_ok=True)
                r = simulate_specialty(cfg, log_path=log)
                r["cell_label"] = label
                r["seed"] = seed
                per_seed.append(r)
                print(f"  spec {label:8s} {arm:11s} {seed}  "
                      f"expert={r['expert_rate']} q={r['quality']}", flush=True)
            cells.extend(per_seed)
    return cells


def run_seal(out: Path, rounds: int) -> list[dict]:
    cells = []
    for label, n_clones, herd in SEAL_CELLS:
        for sealed in (False, True):
            arm = "sealed" if sealed else "open"
            for i, seed in enumerate(SEEDS):
                cfg = SealConfig(rounds=rounds, sealed=sealed, n_clones=n_clones,
                                 herd=herd, seed=seed)
                log = None
                if i == 0:
                    log = out / "seal" / f"{label}_{arm}" / "rows.jsonl"
                    log.parent.mkdir(parents=True, exist_ok=True)
                r = simulate_seal(cfg, log_path=log)
                r["cell_label"] = label
                r["seed"] = seed
                cells.append(r)
                print(f"  seal {label:14s} {arm:6s} {seed}  "
                      f"indep={r['agree_indep_indep']} raw={r['agree_indep_indep_raw']} "
                      f"tp={r['true_positives']}/{r['n_clones']} inf={r['n_informative']}",
                      flush=True)
    return cells


def _pick(rows: list[dict], **kw) -> list[dict]:
    return [r for r in rows
            if all(r.get(k) == v or r.get("config", {}).get(k) == v for k, v in kw.items())]


def _verdicts(spec: list[dict], seal: list[dict]) -> dict:
    v: dict = {}

    # ── 3.1 ────────────────────────────────────────────────────────────
    main_off = _pick(spec, cell_label="main", arm="profile_off")
    main_on = _pick(spec, cell_label="main", arm="profile_on")
    null_off = _pick(spec, cell_label="null", arm="profile_off")
    null_on = _pick(spec, cell_label="null", arm="profile_on")
    e_off, e_on = _agg(main_off, "expert_rate"), _agg(main_on, "expert_rate")
    q_off, q_on = _agg(main_off, "quality"), _agg(main_on, "quality")
    nq_off, nq_on = _agg(null_off, "quality"), _agg(null_on, "quality")
    chance = main_off[0]["chance_rate"] if main_off else None
    v["spec_expert_rate_up"] = {
        "profile_off": e_off, "profile_on": e_on, "chance": chance,
        "pass": bool(e_on["mean"] and e_off["mean"] is not None
                     and e_on["mean"] > e_off["mean"] and e_on["mean"] > (chance or 1)),
    }
    v["spec_quality_not_worse"] = {
        "profile_off": q_off, "profile_on": q_on,
        "delta": (round(q_on["mean"] - q_off["mean"], 4)
                  if q_on["mean"] is not None and q_off["mean"] is not None else None),
        "pass": bool(q_on["mean"] is not None and q_off["mean"] is not None
                     and q_on["mean"] >= q_off["mean"]),
    }
    v["spec_null_control"] = {
        "profile_off": nq_off, "profile_on": nq_on,
        "delta": (round(nq_on["mean"] - nq_off["mean"], 4)
                  if nq_on["mean"] is not None and nq_off["mean"] is not None else None),
        # 沒有真專長時分族不得帶來增益（容差 0.01：不是統計檢定，是健全性）
        "pass": bool(nq_on["mean"] is not None and nq_off["mean"] is not None
                     and abs(nq_on["mean"] - nq_off["mean"]) < 0.01),
    }
    v["spec_budget_exact"] = {
        "pass": all(r["budget_exact"] for r in spec),
        "rejected_reviews": sum(r["rejected_reviews"] for r in spec),
    }

    # ── 3.2 ────────────────────────────────────────────────────────────
    per_cell = {}
    for label, _c, _h in SEAL_CELLS:
        o = _agg(_pick(seal, cell_label=label, arm="open"), "agree_indep_indep")
        s = _agg(_pick(seal, cell_label=label, arm="sealed"), "agree_indep_indep")
        o_raw = _agg(_pick(seal, cell_label=label, arm="open"), "agree_indep_indep_raw")
        s_raw = _agg(_pick(seal, cell_label=label, arm="sealed"), "agree_indep_indep_raw")
        tp_o = _agg(_pick(seal, cell_label=label, arm="open"), "tp_rate")
        tp_s = _agg(_pick(seal, cell_label=label, arm="sealed"), "tp_rate")
        inf_o = _agg(_pick(seal, cell_label=label, arm="open"), "n_informative")
        inf_s = _agg(_pick(seal, cell_label=label, arm="sealed"), "n_informative")
        per_cell[label] = {
            "residual_open": o, "residual_sealed": s,
            "residual_drop": (round(o["mean"] - s["mean"], 4)
                              if o["mean"] is not None and s["mean"] is not None else None),
            "raw_open": o_raw, "raw_sealed": s_raw,
            "raw_drop": (round(o_raw["mean"] - s_raw["mean"], 4)
                         if o_raw["mean"] is not None and s_raw["mean"] is not None else None),
            "tp_rate_open": tp_o, "tp_rate_sealed": tp_s,
            "n_informative_open": inf_o, "n_informative_sealed": inf_s,
            # 鑑別題數差太多 → 兩臂的條件化統計量算在不同的題集上，必須標明
            "denominator_comparable": (
                inf_o["mean"] is not None and inf_s["mean"] is not None
                and inf_s["mean"] > 0 and abs(inf_o["mean"] - inf_s["mean"]) / inf_s["mean"] < 0.1
            ),
        }
    v["seal_per_cell"] = per_cell
    # 主判準跑在**無同源**那一格：那裡任何相關性都只能是架構造成的
    key = "clone0_herd06"
    v["seal_residual_drops"] = {
        "cell": key,
        "drop_conditional": per_cell[key]["residual_drop"],
        "drop_raw": per_cell[key]["raw_drop"],
        "pass": bool(per_cell[key]["residual_drop"] is not None
                     and per_cell[key]["residual_drop"] > 0),
    }
    # 密封臂對 herd 不敏感 ⇒ 瀑布是由建構關閉的，不是由假設關閉的
    sealed_by_herd = {
        lbl: per_cell[lbl]["residual_sealed"]["mean"]
        for lbl in ("clone0_herd00", "clone0_herd06", "clone0_herd09")
    }
    vals = [x for x in sealed_by_herd.values() if x is not None]
    v["seal_invariant_to_herd"] = {
        "sealed_residual_by_herd": sealed_by_herd,
        "spread": round(max(vals) - min(vals), 6) if vals else None,
        "pass": bool(vals and (max(vals) - min(vals)) < 1e-9),
    }
    v["seal_herd_overrides_zero_when_sealed"] = {
        "pass": all(r["herd_overrides"] == 0 for r in seal if r["arm"] == "sealed"),
        "open_total": sum(r["herd_overrides"] for r in seal if r["arm"] == "open"),
    }
    return v


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--spec-rounds", type=int, default=600)
    ap.add_argument("--seal-rounds", type=int, default=200)
    ap.add_argument("--only", choices=["spec", "seal"], default=None)
    args = ap.parse_args()

    out = Path(args.out).expanduser()
    out.mkdir(parents=True, exist_ok=True)

    spec = run_spec(out, args.spec_rounds) if args.only != "seal" else []
    seal = run_seal(out, args.seal_rounds) if args.only != "spec" else []

    if spec:
        with (out / "spec_cells.jsonl").open("w", encoding="utf-8") as f:
            for r in spec:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    if seal:
        with (out / "seal_cells.jsonl").open("w", encoding="utf-8") as f:
            for r in seal:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    if spec and seal:
        summary = {
            "generated": "channel_suite.py",
            "seeds": list(SEEDS),
            "spec_rounds": args.spec_rounds,
            "seal_rounds": args.seal_rounds,
            "spec_cells": [c[0] for c in SPEC_CELLS],
            "seal_cells": [c[0] for c in SEAL_CELLS],
            "verdicts": _verdicts(spec, seal),
        }
        (out / "summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
        print(json.dumps(summary["verdicts"], ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
