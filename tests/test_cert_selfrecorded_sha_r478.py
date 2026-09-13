"""R478 認證段落自記 blob sha 的接線（判準 §七）。

`python3 ops/run_tests_nopytest.py tests/test_cert_selfrecorded_sha_r478.py`

⚠ 不寫死任何絕對數字（附錄增減會讓寫死的數字安靜衰減成永遠紅）。
驗的是四件結構性的事：自記優先真的生效、標題被改寫時**不會低報**、
自記值編造得出來就要大聲壞掉、判準檔自己不會被自己的字面匹配到。
"""
import pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "ops" / "gain"))
import cert_drift_gate as G

PREREG = "DECISION_20260905_R478_CERT_SELF_RECORDED_SHA.md"


def test_recorded_sha_is_preferred_and_measured():
    """真資料：有自記標記的工具格 sha_source 必須是 recorded，且確實量到了（>0）。"""
    rep = G.audit()
    assert rep["slots_recorded"] > 0, rep            # 安靜量不到（第一型）⇒ 這裡就要紅
    for g in rep["groups"]:
        for it in g["items"]:
            if it.get("tool") and it["tool"] in (g.get("recorded") or {}):
                assert it["sha_source"] == "recorded", it
                assert it["blob_at_cert"] == it["blob_at_cert_recorded"], it


def test_rewritten_heading_does_not_underreport():
    """判準 §五 P6 ＝ 本輪的主張，兩個半邊都要成立。

    M9 ＝ 認證標題被改寫（`-S` 反推塌到較晚的 commit）。
    新行為：STALE 格數不變 ＋ mismatch 非空 ＋ rc=2。
    舊行為（M9+M10，忽略自記值）：STALE 掉到 0、rc=0 ＝ **低報**被重現。
    """
    base = G.audit()
    stale0 = base["counts"].get("CERT_STALE", 0)
    assert stale0 > 0, base["counts"]                # 沒有 STALE 就沒東西可低報 ⇒ 這測試空洞
    m9 = G._with_mutant("M9_HEADING_REWRITTEN")
    assert m9["counts"].get("CERT_STALE", 0) == stale0, (stale0, m9["counts"])
    assert len(m9["cert_sha_mismatches"]) > 0 and m9["rc"] == 2, m9["rc"]
    old = G._with_mutant("M9_HEADING_REWRITTEN,M10_IGNORE_RECORDED")
    assert old["counts"].get("CERT_STALE", 0) == 0 and old["rc"] == 0, old["counts"]


def test_fabricated_recorded_sha_is_broken_not_silent():
    """自記值不在該路徑的歷史裡 ⇒ BROKEN_CERT_SHA_NOT_IN_HISTORY ＋ rc=2。"""
    m8 = G._with_mutant("M8_BAD_RECORDED")
    assert m8["counts"].get("BROKEN_CERT_SHA_NOT_IN_HISTORY", 0) > 0, m8["counts"]
    assert m8["rc"] == 2, m8["rc"]


def test_marker_literal_does_not_match_itself():
    """判準檔自己含有標記字面卻沒有認證標題 ⇒ 不准貢獻任何群組（memory：會匹配到自己）。"""
    doc = pathlib.Path(G.ROOT) / PREREG
    assert doc.exists() and ("CERT-" + "BLOB") in doc.read_text(encoding="utf-8")
    assert [g for g in G.audit()["groups"] if g["doc"] == PREREG] == []


def test_malformed_marker_is_loud_not_skipped():
    """格式不合的標記（縮寫 sha）不准安靜跳過，要留下 BROKEN_CERT_SHA_UNPARSEABLE 的料。"""
    good = "- CERT-BLOB `ops/gain/x.py` = `" + "a" * 40 + "`\n"
    bad = "- CERT-BLOB `ops/gain/x.py` = `abc1234`\n"
    rec, mal = G.recorded_in([good, bad], 0, 2)
    assert rec == {"ops/gain/x.py": "a" * 40}, rec
    assert mal == [bad.rstrip("\n")], mal
