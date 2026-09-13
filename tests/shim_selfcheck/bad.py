"""round646 替身自檢（壞的那半）：每一個都必須被抓成 FAIL，一個都不准漏。"""
import os, pytest

def test_raises_when_nothing_is_raised_must_fail():
    with pytest.raises(ValueError):
        pass

def test_raises_with_wrong_match_must_fail():
    with pytest.raises(ValueError, match="zzz"):
        raise ValueError("boom")

def test_tmp_path_assertion_must_fail(tmp_path):
    assert (tmp_path / "nope.txt").exists()

def test_monkeypatch_assertion_must_fail(monkeypatch):
    monkeypatch.setenv("X_SHIM", "1")
    assert os.environ["X_SHIM"] == "2"

@pytest.mark.parametrize("n", [1, 2, 3])
def test_parametrize_third_case_must_fail(n):
    assert n < 3

class TestClassBasedBad:
    def test_class_based_assertion_must_fail(self):
        assert False


def test_approx_must_fail_when_really_different():
    assert 0.3 == pytest.approx(0.31)

def test_approx_sequence_wrong_length_must_fail():
    assert [1.0, 2.0] == pytest.approx([1.0, 2.0, 3.0])

def test_monkeypatch_string_form_assertion_must_fail(monkeypatch):
    import json as _j
    monkeypatch.setattr("json.dumps", lambda *a, **k: "STUBBED")
    assert _j.dumps({}) == "NOT_STUBBED"
