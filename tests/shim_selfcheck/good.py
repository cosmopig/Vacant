"""round646 替身自檢（好的那半）：每個新增能力都要 PASS。"""
import os, pytest

SEEN = []

@pytest.fixture
def widget():
    return {"v": 7}

def test_raises_catches():
    with pytest.raises(ValueError, match="boom"):
        raise ValueError("boom here")

def test_tmp_path_is_a_fresh_writable_dir(tmp_path):
    assert tmp_path.is_dir() and not list(tmp_path.iterdir())
    (tmp_path / "a.txt").write_text("hi")
    SEEN.append(str(tmp_path))

def test_tmp_path_is_not_shared_with_the_previous_test(tmp_path):
    assert str(tmp_path) not in SEEN
    assert not (tmp_path / "a.txt").exists()

def test_monkeypatch_setenv(monkeypatch):
    monkeypatch.setenv("VACANT_SHIM_CHECK", "1")
    assert os.environ["VACANT_SHIM_CHECK"] == "1"

def test_monkeypatch_was_undone_after_the_previous_test():
    assert "VACANT_SHIM_CHECK" not in os.environ

@pytest.mark.parametrize("a,b", [(1, 2), (2, 4), (3, 6)])
def test_parametrize_runs_each_case(a, b):
    assert a * 2 == b

def test_module_fixture_still_works(widget):
    assert widget["v"] == 7

class TestClassBased:
    def test_collected_from_a_class(self):
        assert True
    def test_class_test_can_take_tmp_path(self, tmp_path):
        assert tmp_path.is_dir()


def test_approx_scalar():
    assert 0.1 + 0.2 == pytest.approx(0.3)

def test_approx_sequence_and_dict():
    assert [1.0000001, 2.0] == pytest.approx([1.0, 2.0])
    assert {"a": 0.30000001} == pytest.approx({"a": 0.3})

def test_monkeypatch_string_form_setattr(monkeypatch):
    import json as _j
    monkeypatch.setattr("json.dumps", lambda *a, **k: "STUBBED")
    assert _j.dumps({"a": 1}) == "STUBBED"

def test_monkeypatch_string_form_was_undone():
    import json as _j
    assert _j.dumps({"a": 1}) == '{"a": 1}'

def test_monkeypatch_setattr_on_missing_attr_raises_like_real_pytest(monkeypatch):
    import json as _j
    with pytest.raises(AttributeError):
        monkeypatch.setattr(_j, "__no_such_attr__", 1)
    monkeypatch.setattr(_j, "__no_such_attr__", 1, raising=False)
    assert _j.__no_such_attr__ == 1
