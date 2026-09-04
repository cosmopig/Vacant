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


# ── R469 新增：三個盲點的正向夾具 ──────────────────────────────────
# 牙齒的造法照 memory：讓**兩種語意給出相反答案**，不是「斷言 shim 綁對了」。

@pytest.mark.parametrize("argv", [["up", "--help"], ["down"], []])
def test_parametrize_single_argname_keeps_a_list_value_whole(argv):
    """F1：單一 argname ⇒ 整個 list 是一個參數。

    舊語意（`isinstance(vals,(tuple,list))` 就拆）會把 `["up","--help"]`
    zip 成 argv="up"、把 `[]` 展成零個綁定 ⇒ 這三格在舊量具上必定不是 PASS。
    """
    assert isinstance(argv, list)
    assert argv in (["up", "--help"], ["down"], [])


@pytest.mark.parametrize("pair", [(1, 2), (3, 4)])
def test_parametrize_single_argname_keeps_a_tuple_value_whole(pair):
    """F1：tuple 值同理——單 argname 就不准拆成兩個參數。"""
    assert isinstance(pair, tuple) and len(pair) == 2


@pytest.mark.parametrize("a,b", [(5, 10), (6, 12)])
def test_parametrize_multi_argname_still_unpacks(a, b):
    """F1 的反向護欄：多 argname 這一路**不准**被 F1 弄壞。"""
    assert a * 2 == b


def test_importorskip_returns_the_module_when_it_imports():
    """F2：匯得到就回 module 本身。"""
    j = pytest.importorskip("json")
    assert j.dumps({"a": 1}) == '{"a": 1}'


def test_importorskip_skips_instead_of_erroring_when_missing():
    """F2：匯不到要丟 Skipped（＝這條記 SKIP），不是 ImportError、也不是 ERROR。"""
    try:
        pytest.importorskip("vacant_no_such_module_r469")
    except BaseException as e:
        assert type(e).__name__ == "Skipped", f"應為 Skipped，實際 {type(e).__name__}"
    else:
        raise AssertionError("匯不到的模組竟然沒有 skip")


def test_capsys_captures_stdout_and_stderr(capsys):
    """F3：capsys 抓得到 stdout/stderr。舊量具沒有這個 fixture ⇒ 記 ERROR。"""
    import sys as _s
    print("hello-out")
    print("hello-err", file=_s.stderr)
    cap = capsys.readouterr()
    assert "hello-out" in cap.out
    assert "hello-err" in cap.err


def test_capsys_readouterr_drains_the_buffer(capsys):
    """F3：讀過的不准再讀到一次（真 pytest 的語意）。"""
    print("first")
    assert "first" in capsys.readouterr().out
    assert capsys.readouterr().out == ""
