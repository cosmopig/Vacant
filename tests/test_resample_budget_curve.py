"""重抽預算曲線鏡像的守衛（round 116）。

鏡像 `ops/realrun/resample_budget_curve.json` 由同一把尺（offline_real_signal_replay.py 的
--curve 模式，cap=1..5）對 runs/_replay/c37_final.json 產生。本測試：
  1. 輸入 pin（path + sha256 + rows）；
  2. 鏡像 == 工具對同一輸入的即時重算（cap 逐項相等）；
  3. 只 pin 可引用欄 flag_restart（scorer_used=false；鏡像裡不得出現上界欄）；
  4. 可引用的關鍵數字（n、各 cap 的 pct、K=3 行與 cap=3 鏡像一致）；
  5. 誠實 caveat 在場（offline replay 非 live、cyclic 重用、flat 語義）。
"""

import hashlib
import importlib.util
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TOOL = REPO / "ops" / "realrun" / "offline_real_signal_replay.py"
CURVE = REPO / "ops" / "realrun" / "resample_budget_curve.json"
SINGLE = REPO / "ops" / "realrun" / "offline_real_signal_replay.json"
INPUT = REPO / "runs" / "_replay" / "c37_final.json"
CAPS = ("1", "2", "3", "4", "5")
SUITES = ("polyglot_py", "dabstep", "dabench", "databench")


def _tool():
    spec = importlib.util.spec_from_file_location("offline_real_signal_replay", TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _mirror() -> dict:
    return json.loads(CURVE.read_text(encoding="utf-8"))


def test_input_pinned():
    m = _mirror()
    assert m["schema"] == "vacant.realrun.resample_budget_curve/1"
    assert m["column"] == "flag_restart"
    assert m["input"]["path"] == "runs/_replay/c37_final.json"
    assert m["input"]["sha256"] == hashlib.sha256(INPUT.read_bytes()).hexdigest()
    assert m["input"]["rows"] == 1187
    assert m["input"]["rows_used"] == 1187


def test_mirror_matches_tool_rederivation():
    mod = _tool()
    rows = json.loads(INPUT.read_text(encoding="utf-8"))
    live = mod.curve(rows, [1, 2, 3, 4, 5])
    m = _mirror()
    assert m["caps"] == live["caps"]


def test_only_citable_column_pinned():
    m = _mirror()
    for K in CAPS:
        e = m["caps"][K]
        assert e["all"]["scorer_used"] is False
        assert e["all"]["signal"] == "vacant_findings_empty"
        # 鏡像裡不得混入上界欄（test_restart / oracle_any）
        assert "test_restart" not in e["all"]
        assert "oracle_any" not in e["all"]
        assert set(e["suites"]) == set(SUITES)
        for s in e["suites"].values():
            assert s["scorer_used"] is False


def test_citable_curve_numbers():
    m = _mirror()
    c = m["caps"]
    # n：每題組等權；組數與 cap=3 鏡像一致（68 / 144 / 60 / 59 / ALL 331）
    for K in CAPS:
        assert c[K]["suites"]["polyglot_py"]["units"] == 68
        assert c[K]["suites"]["dabstep"]["units"] == 144
        assert c[K]["suites"]["dabench"]["units"] == 60
        assert c[K]["suites"]["databench"]["units"] == 59
        assert c[K]["all"]["units"] == 331
    # polyglot_py：37.28 → +5.76 → +3.92 → 平（4/5 次無增益）
    assert c["1"]["suites"]["polyglot_py"]["pct"] == 37.28
    assert c["2"]["suites"]["polyglot_py"]["pct"] == 43.04
    assert c["3"]["suites"]["polyglot_py"]["pct"] == 46.96
    assert c["4"]["suites"]["polyglot_py"]["pct"] == 46.96
    assert c["5"]["suites"]["polyglot_py"]["pct"] == 46.96
    # ALL：62.34 → +3.06 → +0.96 → 平
    assert c["1"]["all"]["pct"] == 62.34
    assert c["2"]["all"]["pct"] == 65.40
    assert c["3"]["all"]["pct"] == 66.36
    assert c["4"]["all"]["pct"] == 66.36
    assert c["5"]["all"]["pct"] == 66.36
    # 邊際增益口徑（引用時用）：第 2 次是最大單筆、polyglot 第 3 次仍有意義、4/5 次為 0
    pg = [c[K]["suites"]["polyglot_py"]["pct"] for K in CAPS]
    assert round(pg[1] - pg[0], 2) == 5.76
    assert round(pg[2] - pg[1], 2) == 3.92
    assert pg[3] == pg[4] == pg[2]
    al = [c[K]["all"]["pct"] for K in CAPS]
    assert round(al[1] - al[0], 2) == 3.06
    assert round(al[2] - al[1], 2) == 0.96
    assert al[3] == al[4] == al[2]
    # K=3 行必須與單 cap=3 鏡像一致（同一把尺、同一份輸入）
    single = json.loads(SINGLE.read_text(encoding="utf-8"))
    for suite in SUITES:
        assert c["3"]["suites"][suite]["pct"] == single["suites"][suite]["flag_restart"]["pct"]
    assert c["3"]["all"]["pct"] == single["all"]["flag_restart"]["pct"]


def test_groups_with_n_ge_cap_monotone_and_caveats():
    m = _mirror()
    c = m["caps"]
    # groups_with_n_ge_cap 隨 cap 單調不增（cap 越大，「archived run 數 ≥ cap」的組越少）
    for suite in SUITES:
        vals = [c[K]["suites"][suite]["groups_with_n_ge_cap"] for K in CAPS]
        assert all(a >= b for a, b in zip(vals, vals[1:])), (suite, vals)
        assert vals[0] == c["1"]["suites"][suite]["units"]  # cap=1：所有組都夠
    all_vals = [c[K]["all"]["groups_with_n_ge_cap"] for K in CAPS]
    assert all(a >= b for a, b in zip(all_vals, all_vals[1:])), all_vals
    assert all_vals[0] == 331
    # 誠實 caveat 三條在場
    caveats = " ".join(m["reading"]["caveats"])
    assert "offline replay" in caveats
    assert "reuses archived runs" in caveats
    assert "flatness" in caveats.lower()
