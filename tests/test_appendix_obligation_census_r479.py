"""R479 收官義務普查的接線（判準 §七）。

`python3 ops/run_tests_nopytest.py tests/test_appendix_obligation_census_r479.py`

⚠ 不寫死「幾條不可執行」這種絕對數字（附錄一改就安靜衰減成永遠紅）。
驗的是五件結構性的事：普查本身沒壞、擋門會叫、兩型「安靜量不到」都擋得住、
本判準檔自己不會被自己的字面匹配到、事前預測表沒有被量測後改過。
"""
import pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ops" / "gain"))
import r479_r461_appendix_census as C


def test_census_clean_and_scanned():
    """乾淨基線：verdict OK、掃到 >0 條（第三型安靜量不到＝掃到 0 個目標）、沒讀主 run。"""
    o = C.census()
    assert o["verdict"] == "OK", o["broken"]
    assert o["clauses_scanned"] > 0, o
    assert o["live_run_reads"] == 0, o
    assert o["self_prereg_contributed"] == 0, o


def test_both_calibrations_have_teeth():
    """兩個抽取器都要雙向校準：只有正對照時「什麼都判成立」也會全綠。"""
    o = C.census()
    assert o["calibration"]["positive_control"] is True, o["calibration"]
    assert o["calibration"]["negative_control"] is False, o["calibration"]
    for tool, v in o["keyscan_calibration"].items():
        if isinstance(v, dict):
            assert v["positive_found"] and not v["negative_found"], (tool, v)


def test_type2_silent_undercount_is_loud():
    """型二「量到的數量掉下來」：不追 out.update(...) ⇒ 必須 BROKEN，不准安靜少算鍵。"""
    old = C.MUTANT
    try:
        C.MUTANT = "M11_ignore_update"
        m = C.census()
    finally:
        C.MUTANT = old
    assert m["verdict"] == "BROKEN_KEYSCAN_CALIBRATION", m["verdict"]
    assert m["n_not_executable"] > C.census()["n_not_executable"], m["n_not_executable"]


def test_live_run_read_is_blocked():
    """B3：讀主 run 一次就要大聲叫（run 還在跑，期中資料不是收官資料）。"""
    old = C.MUTANT
    try:
        C.MUTANT = "M5_read_live_run"
        m = C.census()
    finally:
        C.MUTANT = old
    assert m["verdict"] == "BROKEN_LIVE_RUN_READ" and m["live_run_reads"] > 0, m


def test_predictions_match_committed_prereg():
    """事前預測表必須與判準檔 §四 逐格相同（防「量完再改預測」）。"""
    txt = (ROOT / "DECISION_20260905_R479_R461_APPENDIX_OBLIGATION_CENSUS.md").read_text()
    assert txt.count("| C5-1 |") == 1, "判準 §四 的表不見了＝夾具過期，不是通過"
    for cid, klass in C.PRED_CLASS.items():
        row = [l for l in txt.splitlines() if l.startswith(f"| {cid} |")]
        assert len(row) == 1, (cid, row)
        assert klass in row[0], (cid, klass, row[0])
        assert ("**False**" if not C.PRED_EXEC[cid] else "True") in row[0], (cid, row[0])
