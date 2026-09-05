"""R480（A.4／B.3／G 普查）的接線（判準 §五.4）。

`python3 ops/run_tests_nopytest.py tests/test_appendix_bg_census_r480.py`

⚠ 不寫死「幾條 EVALUABLE」這種絕對數字（附錄一改就安靜衰減成永遠紅）。
驗五件結構性的事：乾淨基線沒壞、witness 掃描器雙向校準、兩型「安靜量不到」都擋得住
（型二＝分母漏鍵少算、型三＝掃到 0 個目標）、主 run 讀一次就叫、事前預測表沒被量測後改過。
"""
import pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ops" / "gain"))
import r480_r461_appendix_bg_census as C


def test_census_clean():
    o = C.census()
    assert o["verdict"] == "OK", o["broken"]
    assert o["live_reads"] == 0, o
    assert len(o["clauses"]) == len(C.CLAUSES) > 0, o
    assert all(c["pin_found"] for c in o["clauses"].values()), o


def test_witness_scanner_calibrated_both_ways():
    """只有正對照時「什麼都判 FORCED_GREEN」也會全綠 ⇒ 負對照必須有 witness。"""
    o = C.census()
    assert o["calibration"]["positive_no_witness"] == 0, o["calibration"]
    assert o["calibration"]["negative_has_witness"] > 0, o["calibration"]


def _mut(name):
    old = C.MUTANT
    try:
        C.MUTANT = name
        return C.census()
    finally:
        C.MUTANT = old


def test_type2_silent_undercount_is_loud():
    """型二：分母清單漏掉真正那個鍵 ⇒ 臂解析不出分母 ⇒ 必須 BROKEN，不准安靜少算。"""
    m = _mut("M6_denominator_drops_tasks")
    assert m["verdict"] == "BROKEN_ARM_ACCOUNTING", m["verdict"]
    assert m["unresolved_arms"], m


def test_type3_zero_targets_is_loud():
    """型三：掃描目標 0 個 ⇒ UNSCANNED，且拿掉擋門就不再叫（負對照）。"""
    assert _mut("M2_empty_targets")["verdict"] == "UNSCANNED"
    assert _mut("M3_empty_targets_no_guard")["verdict"] == "OK"


def test_live_run_read_is_loud():
    m = _mut("M1_no_live_guard")
    assert m["verdict"] == "BROKEN_LIVE_READ" and m["live_reads"] > 0, m


def test_predictions_match_committed_prereg():
    """事前預測表必須與判準檔 §三 逐格相同（防「量完再改預測」）。"""
    doc = (ROOT / "DECISION_20260905_R480_R461_APPENDIX_A4_B3_G_CENSUS.md").read_text()
    # ⚠ §一 也有一張 `| A4-1 |` 開頭的表 ⇒ 必須切到 §三 之後再比，否則 count==2 假紅
    assert "## 三、事前預測" in doc, "判準 §三 的標題不見了＝夾具過期，不是通過"
    txt = doc.split("## 三、事前預測", 1)[1].split("## 四、", 1)[0]
    assert txt.count("| A4-1 |") == 1, "判準 §三 的表不見了＝夾具過期，不是通過"
    for cid, klass in C.PRED_CLASS.items():
        row = [l for l in txt.splitlines() if l.startswith(f"| {cid} |")]
        assert len(row) == 1, (cid, row)
        assert klass in row[0], (cid, klass, row[0])
        assert ("**False**" if not C.PRED_EXEC[cid] else "True") in row[0], (cid, row[0])
