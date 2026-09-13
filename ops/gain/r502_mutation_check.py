#!/usr/bin/env python3
"""R502 突變表：判準 §四 事前寫死的六個突變體，在**真資料**上各自被誰看見。

判準：DECISION_20260905_R502_TRIPLE_CONSTRAINED_LADDER_PREREG.md（commit a97b1e8）。
偵測器字串照判準 §四 原樣搬，**不准量完再改**。

三種結果（事前就宣告會有第三格）：
  DETECTED    偵測器照判準的說法翻了
  MISSED      偵測器沒翻（⇒ 該約束在這份資料上零承重，照判準 §四 不准調門檻讓它變綠）
  UNREACHABLE 乾淨執行根本沒走到那段程式碼（本輪第一段判 FORCED ⇒ 第二段被判準跳過）

用法：python3 ops/gain/r502_mutation_check.py
"""
from __future__ import annotations
import json, os, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from ops.gain import r502_triple_constrained_ladder as R502              # noqa: E402

# 判準 §四：突變體 -> (偵測器名稱, 這個偵測器只有在第二段跑得到時才存在)
MUTANTS = [("M1_COMP_TAU_HUGE", "comp_binding_flips_false", True),
           ("M2_COMP_IGNORE", "BROKEN_EQCOMP", True),
           ("M3_SHARE_CONST", "comp_axis_verdict==COMP_FORCED_BY_OTHERS", False),
           ("M4_FORCE_SAME", "headline==POSITION_GONE", True),
           ("M5_DISP_IGNORE", "BROKEN_DISPERSION", True),
           ("M6_ONE_POSITION", "BROKEN_WINDOWS", True)]


def detector_fired(mut: str, clean: dict, out: dict) -> bool:
    """判準 §四 的偵測器。乾淨那格已經是那個值 ⇒ 不算翻（否則是空綠燈）。"""
    if mut == "M1_COMP_TAU_HUGE":
        return (any(clean.get("comp_binding", {}).values())
                and not any(out.get("comp_binding", {}).values()))
    if mut == "M3_SHARE_CONST":
        return (clean.get("comp_axis_verdict") != "COMP_FORCED_BY_OTHERS"
                and out.get("comp_axis_verdict") == "COMP_FORCED_BY_OTHERS")
    if mut == "M4_FORCE_SAME":
        return ("POSITION_GONE" in (out.get("headlines") or {}).values()
                and "POSITION_GONE" not in (clean.get("headlines") or {}).values())
    return mut_blocker(mut) in out["blockers"] and mut_blocker(mut) not in clean["blockers"]


def mut_blocker(mut: str) -> str:
    return {"M2_COMP_IGNORE": "BROKEN_EQCOMP", "M5_DISP_IGNORE": "BROKEN_DISPERSION",
            "M6_ONE_POSITION": "BROKEN_WINDOWS"}[mut]


def main() -> int:
    os.environ.pop("R502_MUTANT", None)
    clean = R502.census()
    rows = []
    for mut, det, needs_stage2 in MUTANTS:
        os.environ["R502_MUTANT"] = mut
        try:
            out = R502.census()
            err = None
        except Exception as e:                       # crash 收場不算偵測到（memory）
            out, err = {"verdict": None, "blockers": [], "headlines": {}}, f"{type(e).__name__}: {e}"
        finally:
            os.environ.pop("R502_MUTANT", None)
        if err is not None:
            res = "BROKEN_CRASH"
        elif needs_stage2 and not clean["stage2_ran"]:
            res = "UNREACHABLE"
        elif detector_fired(mut, clean, out):
            res = "DETECTED"
        else:
            res = "MISSED"
        rows.append({"mutant": mut, "declared_detector": det, "result": res,
                     "verdict": out.get("verdict"), "error": err,
                     # 事後附記（不是判準）：這個突變體到底動了什麼量
                     "posthoc_band_max_spread": {
                         k: v.get("band_max_spread")
                         for k, v in (out.get("comp_axis") or {}).items()}})
    summary = {"clean_verdict": clean["verdict"], "clean_comp_axis": clean["comp_axis_verdict"],
               "clean_stage2_ran": clean["stage2_ran"],
               "clean_band_max_spread": {k: v["band_max_spread"]
                                         for k, v in clean["comp_axis"].items()},
               "counts": {r: sum(1 for x in rows if x["result"] == r)
                          for r in ("DETECTED", "MISSED", "UNREACHABLE", "BROKEN_CRASH")},
               "rows": rows}
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
