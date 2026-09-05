#!/usr/bin/env python3
"""R492：R461 收官路徑（P-R461-1／P-R461-2）的**合取項資訊量普查**。

判準：DECISION_20260905_R492_R461_CLOSING_CONJUNCT_INFORMATIVENESS.md

問的問題不是「這條預測會不會命中」，而是**「這個合取項在這個合取式裡帶不帶資訊」**：
若「其他合取項全為真」蘊含「它也為真」，它就從來沒有機會單獨紅過 ⇒ `FORCED_BY_OTHERS`。

鐵律遵守：
  * 判決運算式一律呼叫 `paired_ci.py` 自己的 `diff_ci()`／`verdict()`，不重寫一份。
  * 判決字串字面用 `ast.get_source_segment` 從原始碼逐字取，對不上就 CENSUS_BROKEN。
  * 狀態空間**窮舉**，不隨機抽樣（「抽不到」≠「恆等式」）。
  * G-LIVE：不准讀主 run（它還沒收官，讀了就破壞盲測）。
"""
from __future__ import annotations

import argparse
import ast
import builtins
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PAIRED_CI = ROOT / "ops" / "gain" / "replay" / "paired_ci.py"
sys.path.insert(0, str(PAIRED_CI.parent))

import paired_ci  # noqa: E402

LIVE_RUN = "g_r461_lcb3_three_arm"
N_PINNED = 189                      # R461 §四 釘死的 --n
EXPECTED_VERDICTS = {"ON_WINS", "RULED_OUT", "UNINFORMATIVE",
                     "NON_INFERIOR_BUT_UNRESOLVED"}
MIN_STATES = 10000                  # 判準 §六 P-6：掃到 0 個目標＝第三型安靜量不到


def _mut() -> str:
    """突變旗標一律在**函式內部**讀（模組層讀＝突變永遠不生效）。"""
    return os.environ.get("R492_MUTANT", "")


# ---------------------------------------------------------------- G-LIVE 擋門
class LiveRunReadError(RuntimeError):
    pass


_REAL_OPEN = builtins.open


def install_live_gate() -> None:
    """判準 §五：任何開檔路徑含主 run 目錄名 ⇒ RuntimeError。"""
    if _mut() == "M3":              # 突變點：拿掉擋門
        return

    def guarded(file, *a, **kw):
        if LIVE_RUN in str(file):
            raise LiveRunReadError(f"G-LIVE: 不准讀活著的主 run: {file}")
        return _REAL_OPEN(file, *a, **kw)

    builtins.open = guarded


def uninstall_live_gate() -> None:
    builtins.open = _REAL_OPEN


# ------------------------------------------------------- 判決詞彙表（ast 逐字）
def verdict_vocabulary() -> list[str]:
    src = _REAL_OPEN(PAIRED_CI, encoding="utf-8").read()
    tree = ast.parse(src)
    out: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "verdict":
            for sub in ast.walk(node):
                if isinstance(sub, ast.Return) and sub.value is not None:
                    seg = ast.get_source_segment(src, sub.value)
                    if seg is not None and seg.startswith(('"', "'")):
                        out.append(ast.literal_eval(seg))
    return sorted(set(out))


# -------------------------------------------------------------- 狀態空間窮舉
def enumerate_states(n: int) -> list[dict]:
    """窮舉 b + c <= n 的所有整數格，每格用 paired_ci 自己的函式算量。"""
    cap = n
    if _mut() == "M2":              # 突變點：把狀態空間砍到只剩小 n_d
        cap = 5
    states = []
    for nd in range(0, cap + 1):
        for b in range(0, nd + 1):
            c = nd - b
            d = paired_ci.diff_ci(b, c, n)
            lo_pp, hi_pp = d["lo"] * 100.0, d["hi"] * 100.0
            states.append({
                "b": b, "c": c, "n": n,
                "delta_pp": d["delta"] * 100.0,
                "p": d["p_mcnemar"],
                "lo_pp": lo_pp, "hi_pp": hi_pp,
                "verdict": paired_ci.verdict(lo_pp, hi_pp),
            })
    return states


# ------------------------------------------------------------------ 合取式
def conjuncts_for(pred: str) -> dict:
    """逐字對應 R461 §四＋附錄 B.2／C.2 的合取式。"""
    if pred == "P-R461-1":
        return {
            "A1_delta_in_3_20": lambda s: 3.0 <= s["delta_pp"] <= 20.0,
            "A2_p_lt_0.05": lambda s: s["p"] < 0.05,
            "A3_verdict_ON_WINS": lambda s: s["verdict"] == "ON_WINS",
        }
    if pred == "P-R461-2":
        return {
            "B1_delta_in_8_28": lambda s: 8.0 <= s["delta_pp"] <= 28.0,
            "B2_p_lt_0.05": lambda s: s["p"] < 0.05,
            "B3_verdict_ON_WINS": lambda s: s["verdict"] == "ON_WINS",
        }
    raise KeyError(pred)


def classify(states: list[dict], conj: dict) -> dict:
    """對每個合取項 X：找「其他項全真 ∧ X 假」的反例。"""
    out = {}
    for name, fn in conj.items():
        others = [f for k, f in conj.items() if k != name]
        n_others_true = 0
        witness = None
        for s in states:
            if not all(f(s) for f in others):
                continue
            n_others_true += 1
            if _mut() == "M4":      # 突變點：永遠找不到反例（什麼都判 FORCED）
                continue
            if not fn(s) and witness is None:
                witness = dict(s)
        if n_others_true == 0:
            cls = "UNSCANNED"
        elif witness is None:
            cls = "FORCED_BY_OTHERS"
        else:
            cls = "EVALUABLE"
        out[name] = {"class": cls, "n_others_true": n_others_true, "witness": witness}
    return out


# ------------------------------------------------------------------ 校準對照
def calibration(states: list[dict]) -> dict:
    base = conjuncts_for("P-R461-1")
    pos = dict(base); pos["C_POS_p_le_1"] = lambda s: s["p"] <= 1.0
    neg = dict(base); neg["C_NEG_delta_gt_12.5"] = lambda s: s["delta_pp"] > 12.5
    return {
        "C_POS": classify(states, pos)["C_POS_p_le_1"],
        "C_NEG": classify(states, neg)["C_NEG_delta_gt_12.5"],
    }


# --------------------------------------------------------------------- 主流程
def run(n: int) -> dict:
    out: dict = {"n": n, "live_reads": 0, "blockers": []}

    vocab = verdict_vocabulary()
    out["verdict_vocabulary"] = vocab
    if set(vocab) != EXPECTED_VERDICTS:
        out["blockers"].append(f"VERDICT_VOCAB_DRIFT: {vocab}")
    if "ON_WINS" not in vocab:
        out["blockers"].append("ON_WINS_NOT_EMITTED")

    states = enumerate_states(n)
    out["n_states_scanned"] = len(states)
    if len(states) < MIN_STATES:
        out["blockers"].append(f"TOO_FEW_STATES: {len(states)} < {MIN_STATES}")

    cal = calibration(states)
    out["calibration"] = cal
    if cal["C_POS"]["class"] != "FORCED_BY_OTHERS":
        out["blockers"].append(f"C_POS_MISBEHAVED: {cal['C_POS']['class']}")
    if cal["C_NEG"]["class"] != "EVALUABLE":
        out["blockers"].append(f"C_NEG_MISBEHAVED: {cal['C_NEG']['class']}")

    preds = {}
    for p in ("P-R461-1", "P-R461-2"):
        preds[p] = classify(states, conjuncts_for(p))
    preds["P-R461-3"] = {"_whole": {"class": "UNSCANNED_DIFFERENT_EMITTER",
                                    "n_others_true": 0, "witness": None}}
    out["predictions"] = preds

    for p, cs in preds.items():
        for name, r in cs.items():
            if r["class"] == "UNSCANNED":
                out["blockers"].append(f"UNSCANNED: {p}.{name}")

    out["min_paired_gate_active"] = n < paired_ci.MIN_PAIRED
    out["verdict"] = "CENSUS_BROKEN" if out["blockers"] else "CENSUS_OK"
    return out


# --------------------------------------------------------------------- selftest
def selftest() -> int:
    fails: list[str] = []

    # A: 判決詞彙表逐字取得到，且含 ON_WINS
    v = verdict_vocabulary()
    if set(v) != EXPECTED_VERDICTS:
        fails.append(f"A: 詞彙表 {v}")

    # B: G-LIVE 擋門真的擋得住（正對照）
    install_live_gate()
    try:
        try:
            open(f"runs/{LIVE_RUN}/rows.jsonl")
            fails.append("B: G-LIVE 沒擋住主 run")
        except LiveRunReadError:
            pass
        # C: 擋門不誤傷別的路徑
        try:
            open(PAIRED_CI, encoding="utf-8").close()
        except LiveRunReadError:
            fails.append("C: G-LIVE 誤傷了無關路徑")
    finally:
        uninstall_live_gate()

    # D: 分類器在**手造**的小狀態集上兩個方向都到得了
    toy = [{"x": 1, "y": 1}, {"x": 1, "y": 0}]
    cj = {"X": lambda s: s["x"] == 1, "Y": lambda s: s["y"] == 1}
    r = classify(toy, cj)
    if r["Y"]["class"] != "EVALUABLE":
        fails.append(f"D: Y 應 EVALUABLE，得 {r['Y']['class']}")
    if r["X"]["class"] != "FORCED_BY_OTHERS":
        fails.append(f"D: X 應 FORCED_BY_OTHERS，得 {r['X']['class']}")

    # E: 「其他項全假」⇒ UNSCANNED，不是綠燈
    r2 = classify([{"x": 0, "y": 0}], {"X": lambda s: s["x"] == 1,
                                       "Y": lambda s: s["y"] == 1})
    if r2["X"]["class"] != "UNSCANNED":
        fails.append(f"E: 應 UNSCANNED，得 {r2['X']['class']}")

    # F: diff_ci/verdict 真的來自 paired_ci（不是本檔重寫）
    # 四個判決名各釘一格（RULED_OUT 在 UNINFORMATIVE 之前判，順序本身也釘住）
    for lo, hi, want in ((1.0, 9.0, "ON_WINS"), (-9.0, 1.0, "RULED_OUT"),
                         (-9.0, 9.0, "UNINFORMATIVE"), (-1.0, 9.0, "NON_INFERIOR_BUT_UNRESOLVED")):
        got = paired_ci.verdict(lo, hi)
        if got != want:
            fails.append(f"F: verdict({lo},{hi}) 應 {want}，得 {got}")

    for m in fails:
        print("SELFTEST FAIL:", m)
    print("selftest:", "all passed" if not fails else f"{len(fails)} failed",
          "(A 詞彙表 B/C G-LIVE 兩向 D 分類器兩向 E UNSCANNED F 被測函式出處)")
    return 1 if fails else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=N_PINNED)
    ap.add_argument("--sweep", action="store_true", help="補充：n ∈ {60,100,189}")
    ap.add_argument("--json")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()

    install_live_gate()
    try:
        out = run(a.n)
        if a.sweep:
            out["supplementary_sweep"] = {
                str(k): {p: {c: r["class"] for c, r in cs.items()}
                         for p, cs in run(k)["predictions"].items()}
                for k in (60, 100)
            }
    finally:
        uninstall_live_gate()

    if a.json:
        Path(a.json).parent.mkdir(parents=True, exist_ok=True)
        _REAL_OPEN(a.json, "w", encoding="utf-8").write(json.dumps(out, indent=2, ensure_ascii=False))
    print(json.dumps({k: out[k] for k in
                      ("verdict", "n", "n_states_scanned", "live_reads", "blockers")},
                     ensure_ascii=False))
    for p, cs in out["predictions"].items():
        for name, r in cs.items():
            w = r["witness"]
            wt = "" if not w else f"  witness b={w['b']} c={w['c']} Δ={w['delta_pp']:.3f}pp p={w['p']:.5f} v={w['verdict']}"
            print(f"  {p:<10} {name:<22} {r['class']:<26} others_true={r['n_others_true']}{wt}")
    print(f"  calibration  C_POS={out['calibration']['C_POS']['class']}  "
          f"C_NEG={out['calibration']['C_NEG']['class']}")
    return 0 if out["verdict"] == "CENSUS_OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
