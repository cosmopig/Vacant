"""R477 認證漂移擋門的接線（判準 §八）。

這台沒有 pytest ⇒ 用 `python3 ops/run_tests_nopytest.py tests/test_cert_drift_gate_r477.py`。
⚠ 這裡**不寫死任何絕對數字**（認證格數會隨附錄增減而變，寫死＝安靜衰減成永遠紅）；
   驗的是「偵測器有牙齒」與「rc 語意自洽」兩件結構性的事。
"""
import pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "ops" / "gain"))
import cert_drift_gate as G


def _spec_rc(rep):
    """判準 §六 的 rc 語意，在測試側**獨立**再轉錄一次（不呼叫被測模組的同一份）。"""
    if rep["docs_scanned"] == 0:
        return 2
    if rep.get("cert_sha_mismatches"):        # R478 §三 新增的一條（只加不改）
        return 2
    if any(k.startswith("BROKEN") for k in rep["counts"]):
        return 2
    if rep["counts"].get("CERT_STALE"):
        return 1
    return 0 if rep["counts"].get("CERT_FRESH") else 2


def test_selftest_passes():
    """12 條自檢（含真資料雙向校準與 M1–M7）全綠，否則這把尺不能用。"""
    assert G.selftest() == 0


def test_rc_semantics_on_real_data():
    rep = G.audit()
    assert rep["rc"] == _spec_rc(rep), (rep["rc"], rep["counts"])
    assert rep["live_run_reads"] == 0
    assert rep["docs_scanned"] > 0 and rep["cert_headings"] > 0   # 安靜量不到 ⇒ 這裡就要紅


def test_exemption_cannot_silence_stale():
    """豁免名單只准處理 BROKEN_NO_TOOLS；碰到 CERT_STALE 必須拒絕並記數。"""
    groups = [dict(doc="D.md", heads=[dict(line=1, text="# x 原樣跑過")],
                   items=[dict(tool="t.py", verdict="CERT_STALE"),
                          dict(tool=None, verdict="BROKEN_NO_TOOLS")])]
    refused = G.apply_exemptions(groups, [dict(doc="D.md", line=1, reason="test")])
    verdicts = [it["verdict"] for it in groups[0]["items"]]
    assert verdicts == ["CERT_STALE", "TRIAGED_NOT_A_CERT"], verdicts
    assert refused == 1
