"""極簡 pytest 代打：在沒有 pytest 的機器上，把 `tests/` 真的**驗到**。

這支在架構裡承重什麼：紀錄紅線（09 §3.5／HANDOFF §8）說「只數產物、不看返回值」，
而測試報告本身就是一種產物——**報告錯了，後面每一輪的「全過」都不能用**。
執行端這台裝不了 pytest（沒有 pip、裝要 sudo），先前的臨時 runner 只收模組層級的
`def test_*`，於是 `tests/test_research.py` 那 19 條寫在 class 裡的統計測試
（含上一輪被當承重件用的 `holm_bonferroni`）**從來沒有執行過，而報告顯示「全過」**。
這支存在的理由就是把那種假通過關掉。

三條設計紀律，每一條都對應一種假通過：

1. **fail-closed。** stub 沒實作到的 `pytest.*` 一律 `AttributeError`，該檔報
   import 失敗並列名。**絕不因為「stub 沒有這個東西」而讓測試靜默放行。**
2. **SKIP 不是 PASS。** 跳過的測試逐條列名計數，不併進 passed；未知 fixture、
   `skipif` 為真、`pytest.skip()` 全都算 skipped。
3. **探針先驗。** 每次執行都先跑 `--selftest`：一組**事先寫死預期結果**的合成
   測試，含負面題（`raises` 沒 raise 必須判 failed、`skipif(True)` 必須判
   skipped 而不是 passed、未知 fixture 必須列名）。自驗不過就 exit 1，
   不准拿去量未知的。

**這支不是 pytest。在這裡通過 ≠ 在 pytest 下通過。** 已知不等價：沒有 conftest／
plugin、沒有 fixture scope 的 teardown（只有 module 快取）、沒有 assert 改寫
（失敗訊息較差，pass/fail 語意相同）、收集順序照原始碼行號。

用法：
    PYTHONPATH=. python3 examples/minitest.py                 # 自驗 ＋ 全部 tests/
    PYTHONPATH=. python3 examples/minitest.py tests/test_research.py
    PYTHONPATH=. python3 examples/minitest.py --selftest-only  # 只驗探針
"""

from __future__ import annotations

import importlib.util
import inspect
import io
import os
import re
import shutil
import sys
import tempfile
import traceback
import types
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


# --------------------------------------------------------------------------
# stub pytest
# --------------------------------------------------------------------------

class Failed(Exception):
    """測試明確判失敗（pytest.fail／raises 沒抓到東西）。"""


class Skipped(Exception):
    """測試被跳過。**跳過不算通過。**"""


class MissingFixture(Exception):
    """要一個我沒有的 fixture ⇒ 該測試 skipped 並列名，不准當成 passed。"""


class _ExceptionInfo:
    """`with pytest.raises(...) as ei` 的 ei。"""

    def __init__(self):
        self.value = None
        self.type = None
        self.traceback = None

    def __str__(self):  # 少數測試會 str(ei)
        return str(self.value)


class _Raises:
    def __init__(self, expected, match=None):
        self.expected = expected
        self.match = match
        self.info = _ExceptionInfo()

    def __enter__(self):
        return self.info

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            name = getattr(self.expected, "__name__", str(self.expected))
            raise Failed(f"DID NOT RAISE {name}")
        if not issubclass(exc_type, self.expected):
            return False  # 型別不合 ⇒ 讓它往外炸，算 failed
        if self.match is not None and re.search(self.match, str(exc)) is None:
            raise Failed(
                f"例外訊息不符 match={self.match!r}：實際 {str(exc)!r}")
        self.info.value = exc
        self.info.type = exc_type
        self.info.traceback = tb
        return True


def _raises(expected, match=None):
    return _Raises(expected, match)


class _Approx:
    """pytest.approx 的最小相容實作。

    語意照 pytest：只給 `abs` 時只看絕對容差；只給 `rel` 時
    容差＝max(rel·|expected|, 1e-12)；都不給時 rel=1e-6、abs=1e-12。
    """

    def __init__(self, expected, rel=None, abs=None):
        self.expected = expected
        self.rel = rel
        self.abs = abs

    def _tol(self, expected):
        if self.abs is not None and self.rel is None:
            return self.abs
        rel = 1e-6 if self.rel is None else self.rel
        abs_ = 1e-12 if self.abs is None else self.abs
        return max(rel * builtins_abs(expected), abs_)

    def _scalar_eq(self, actual, expected):
        try:
            return builtins_abs(actual - expected) <= self._tol(expected)
        except TypeError:
            return actual == expected

    def __eq__(self, actual):
        exp = self.expected
        if isinstance(exp, dict):
            if not isinstance(actual, dict) or set(actual) != set(exp):
                return False
            return all(self._scalar_eq(actual[k], exp[k]) for k in exp)
        if isinstance(exp, (list, tuple)):
            if not isinstance(actual, (list, tuple)) or len(actual) != len(exp):
                return False
            return all(self._scalar_eq(a, e) for a, e in zip(actual, exp))
        return self._scalar_eq(actual, exp)

    def __ne__(self, actual):
        return not self.__eq__(actual)

    def __repr__(self):
        return f"approx({self.expected!r}, rel={self.rel}, abs={self.abs})"


builtins_abs = abs  # _Approx 內部把 abs 當參數名用掉了


@dataclass
class _Mark:
    """一個 mark；可當 decorator 用，也可以放在 module 的 `pytestmark`。"""

    kind: str
    args: tuple = ()
    kwargs: dict = field(default_factory=dict)

    def __call__(self, fn):
        marks = list(getattr(fn, "_mt_marks", []))
        marks.append(self)
        fn._mt_marks = marks
        return fn


def _parametrize(argnames, argvalues, **kwargs):
    if kwargs:
        raise AttributeError(
            f"minitest 沒有實作 parametrize 的 {sorted(kwargs)}（fail-closed）")
    names = ([n.strip() for n in argnames.split(",")]
             if isinstance(argnames, str) else list(argnames))

    def deco(fn):
        sets = list(getattr(fn, "_mt_parametrize", []))
        sets.append((names, list(argvalues)))
        fn._mt_parametrize = sets
        return fn

    return deco


class _MarkFactory:
    """`pytest.mark.*`。**沒實作的 mark 直接 AttributeError**（fail-closed）——
    靜默忽略一個未知 mark，等於讓它標記的測試在錯誤的條件下被算成通過。"""

    def parametrize(self, argnames, argvalues, **kw):
        return _parametrize(argnames, argvalues, **kw)

    def skipif(self, condition, reason="(未給 reason)"):
        return _Mark("skipif", (condition,), {"reason": reason})

    def __getattr__(self, name):
        raise AttributeError(
            f"minitest 的 pytest stub 沒有實作 mark.{name}（fail-closed："
            f"寧可讓這個檔案報 import 失敗，也不要讓它靜默通過）")


def _fixture(func=None, *, scope="function", **kwargs):
    if kwargs:
        raise AttributeError(
            f"minitest 沒有實作 fixture 的 {sorted(kwargs)}（fail-closed）")

    def deco(fn):
        fn._mt_fixture = True
        fn._mt_fixture_scope = scope
        return fn

    return deco(func) if func is not None else deco


def _fail(msg="(未給訊息)", pytrace=True):
    raise Failed(msg)


def _skip(reason="(未給 reason)", allow_module_level=False):
    raise Skipped(reason)


def install_stub_pytest():
    """把 stub 塞進 sys.modules['pytest']；回傳它。"""
    mod = types.ModuleType("pytest")
    mod.raises = _raises
    mod.approx = _Approx
    mod.fail = _fail
    mod.skip = _skip
    mod.fixture = _fixture
    mod.mark = _MarkFactory()
    mod.__minitest_stub__ = True
    sys.modules["pytest"] = mod
    return mod


# --------------------------------------------------------------------------
# 內建 fixture
# --------------------------------------------------------------------------

_NOTSET = object()


def _resolve_dotted(path):
    """把 "vacant.controller.atomic_write_text" 解成 (module_or_obj, "attr")。

    照 pytest 的作法：先找**最長的可 import 前綴**，剩下的用 getattr 走下去。
    只用 rpartition 會在 "mod.Class.method" 這種路徑上解錯。
    """
    parts = path.split(".")
    if len(parts) < 2:
        raise AttributeError(f"monkeypatch.setattr 的目標要有點號：{path!r}")
    obj = None
    used = 0
    for i in range(len(parts) - 1, 0, -1):
        try:
            obj = importlib.import_module(".".join(parts[:i]))
            used = i
            break
        except ImportError:
            continue
    if obj is None:
        raise ImportError(f"無法 import {path!r} 的任何前綴")
    for p in parts[used:-1]:
        obj = getattr(obj, p)
    return obj, parts[-1]


class _MonkeyPatch:
    def __init__(self):
        self._undo = []

    def setattr(self, target, name=_NOTSET, value=_NOTSET, raising=True):
        if isinstance(target, str):
            if value is _NOTSET:          # 字串形式：setattr("a.b.c", value)
                target, name, value = (*_resolve_dotted(target), name)
            else:
                raise AttributeError(
                    "monkeypatch.setattr 字串形式不接受三個位置參數")
        if name is _NOTSET or value is _NOTSET:
            raise AttributeError("monkeypatch.setattr 參數不足")
        had = hasattr(target, name)
        if not had and raising:
            raise AttributeError(f"{target!r} 沒有屬性 {name}")
        old = getattr(target, name, None)
        self._undo.append(
            (lambda: setattr(target, name, old)) if had
            else (lambda: delattr(target, name)))
        setattr(target, name, value)

    def delattr(self, target, name, raising=True):
        if not hasattr(target, name):
            if raising:
                raise AttributeError(f"{target!r} 沒有屬性 {name}")
            return
        old = getattr(target, name)
        self._undo.append(lambda: setattr(target, name, old))
        delattr(target, name)

    def setenv(self, name, value, prepend=None):
        if prepend is not None:
            raise AttributeError("minitest 沒有實作 setenv(prepend=)（fail-closed）")
        old = os.environ.get(name)
        self._undo.append(
            (lambda: os.environ.__setitem__(name, old)) if old is not None
            else (lambda: os.environ.pop(name, None)))
        os.environ[name] = str(value)

    def delenv(self, name, raising=True):
        if name not in os.environ:
            if raising:
                raise KeyError(name)
            return
        old = os.environ[name]
        self._undo.append(lambda: os.environ.__setitem__(name, old))
        del os.environ[name]

    def setitem(self, dic, name, value):
        had = name in dic
        old = dic.get(name)
        self._undo.append(
            (lambda: dic.__setitem__(name, old)) if had
            else (lambda: dic.pop(name, None)))
        dic[name] = value

    def delitem(self, dic, name, raising=True):
        if name not in dic:
            if raising:
                raise KeyError(name)
            return
        old = dic[name]
        self._undo.append(lambda: dic.__setitem__(name, old))
        del dic[name]

    def chdir(self, path):
        old = os.getcwd()
        self._undo.append(lambda: os.chdir(old))
        os.chdir(path)

    def syspath_prepend(self, path):
        old = list(sys.path)
        self._undo.append(lambda: sys.path.__setitem__(slice(None), old))
        sys.path.insert(0, str(path))

    def undo(self):
        while self._undo:
            self._undo.pop()()


class _CapResult:
    def __init__(self, out, err):
        self.out = out
        self.err = err

    def __iter__(self):  # cap.out, cap.err = capsys.readouterr()
        return iter((self.out, self.err))


class _CapSys:
    def __init__(self):
        self._out = io.StringIO()
        self._err = io.StringIO()
        self._saved = None

    def start(self):
        self._saved = (sys.stdout, sys.stderr)
        sys.stdout, sys.stderr = self._out, self._err

    def stop(self):
        if self._saved:
            sys.stdout, sys.stderr = self._saved
            self._saved = None

    def readouterr(self):
        out, err = self._out.getvalue(), self._err.getvalue()
        self._out.seek(0), self._out.truncate(0)
        self._err.seek(0), self._err.truncate(0)
        return _CapResult(out, err)


# --------------------------------------------------------------------------
# 收集與執行
# --------------------------------------------------------------------------

@dataclass
class Case:
    id: str
    fn: object
    instance: object          # class 測試的 self，模組層級為 None
    params: dict
    marks: list
    lineno: int


@dataclass
class Outcome:
    id: str
    status: str               # passed / failed / skipped
    reason: str = ""


def _expand_params(fn):
    """把疊起來的 parametrize 展成笛卡兒積；沒有就回傳 [{}]。"""
    sets = getattr(fn, "_mt_parametrize", [])
    combos = [{}]
    for names, values in reversed(sets):   # 先套用的（最靠近 def 的）變化最快
        nxt = []
        for combo in combos:
            for v in values:
                vals = (v,) if len(names) == 1 else tuple(v)
                if len(vals) != len(names):
                    raise ValueError(
                        f"parametrize 名數 {names} 與值 {v!r} 對不上")
                nxt.append({**combo, **dict(zip(names, vals))})
        combos = nxt
    return combos


def _case_id(base, params):
    if not params:
        return base
    inner = ",".join(f"{k}={params[k]!r}" for k in sorted(params))
    return f"{base}[{inner}]"


def collect(mod):
    """收集：模組層級 `test_*` ＋ `Test*` class 的 `test_*` method。照行號排序。"""
    cases = []
    module_marks = getattr(mod, "pytestmark", [])
    if isinstance(module_marks, _Mark):
        module_marks = [module_marks]

    def add(fn, base, instance, lineno):
        marks = list(module_marks) + list(getattr(fn, "_mt_marks", []))
        for params in _expand_params(fn):
            cases.append(Case(_case_id(base, params), fn, instance,
                              params, marks, lineno))

    for name, obj in vars(mod).items():
        if name.startswith("test_") and inspect.isfunction(obj):
            add(obj, name, None, obj.__code__.co_firstlineno)
        elif name.startswith("Test") and inspect.isclass(obj):
            if obj.__module__ != mod.__name__:
                continue
            inst = obj()
            for mname, mobj in vars(obj).items():
                if mname.startswith("test_") and inspect.isfunction(mobj):
                    add(mobj, f"{name}::{mname}", inst,
                        mobj.__code__.co_firstlineno)
    cases.sort(key=lambda c: (c.lineno, c.id))
    return cases


def _user_fixtures(mod):
    return {n: o for n, o in vars(mod).items()
            if callable(o) and getattr(o, "_mt_fixture", False)}


def _resolve_fixture(name, mod, fixtures, cache, teardowns, stack):
    """遞迴解 fixture。未知的 ⇒ MissingFixture ⇒ 該測試 skipped 並列名。"""
    if name == "tmp_path":
        p = Path(tempfile.mkdtemp(prefix="minitest-"))
        teardowns.append(lambda: shutil.rmtree(p, ignore_errors=True))
        return p
    if name == "monkeypatch":
        mp = _MonkeyPatch()
        teardowns.append(mp.undo)
        return mp
    if name == "capsys":
        cap = _CapSys()
        cap.start()
        teardowns.append(cap.stop)
        return cap
    if name not in fixtures:
        raise MissingFixture(name)
    if name in stack:
        raise ValueError(f"fixture 相依成環：{' -> '.join(stack)} -> {name}")
    fn = fixtures[name]
    scope = getattr(fn, "_mt_fixture_scope", "function")
    if scope in ("module", "session", "package") and name in cache:
        return cache[name]
    kw = {p: _resolve_fixture(p, mod, fixtures, cache, teardowns, stack + [name])
          for p in inspect.signature(fn).parameters}
    val = fn(**kw)
    if scope in ("module", "session", "package"):
        cache[name] = val
    return val


def run_case(case, mod, fixtures, cache):
    for m in case.marks:
        if m.kind == "skipif" and m.args[0]:
            return Outcome(case.id, "skipped",
                           f"skipif: {m.kwargs.get('reason')}")
    teardowns = []
    try:
        kw = dict(case.params)
        for p in inspect.signature(case.fn).parameters:
            if p == "self" or p in kw:
                continue
            kw[p] = _resolve_fixture(p, mod, fixtures, cache, teardowns, [])
    except MissingFixture as e:
        for t in reversed(teardowns):
            t()
        return Outcome(case.id, "skipped", f"缺 fixture: {e.args[0]}")
    except Exception:
        for t in reversed(teardowns):
            t()
        return Outcome(case.id, "failed",
                       "fixture 建立失敗\n" + traceback.format_exc())
    try:
        if case.instance is not None:
            case.fn(case.instance, **kw)
        else:
            case.fn(**kw)
        return Outcome(case.id, "passed")
    except Skipped as e:
        return Outcome(case.id, "skipped", f"pytest.skip: {e}")
    except Exception:
        return Outcome(case.id, "failed", traceback.format_exc())
    finally:
        for t in reversed(teardowns):
            try:
                t()
            except Exception:
                pass


def run_file(path):
    """回傳 (outcomes, import_error_or_None)。"""
    path = Path(path)
    name = f"_mt_{path.stem}"
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
    except Skipped as e:
        return [], f"模組層級 skip：{e}"
    except Exception:
        return [], traceback.format_exc()
    try:
        cases = collect(mod)
    except Exception:
        return [], "收集失敗\n" + traceback.format_exc()
    fixtures = _user_fixtures(mod)
    cache = {}
    out = []
    for c in cases:
        try:
            out.append(run_case(c, mod, fixtures, cache))
        finally:
            if not isinstance(sys.stdout, io.TextIOWrapper):
                pass  # capsys 的還原在 teardown 做；這裡只是保險註記
    return out, None


def report(path, outcomes, err, verbose=True):
    label = Path(path).name
    if err:
        print(f"{label}: ERROR（import／收集失敗）")
        if verbose:
            for line in err.strip().splitlines()[-6:]:
                print(f"    {line}")
        return {"file": label, "error": True, "passed": 0,
                "failed": 0, "skipped": 0, "collected": 0}
    p = [o for o in outcomes if o.status == "passed"]
    f = [o for o in outcomes if o.status == "failed"]
    s = [o for o in outcomes if o.status == "skipped"]
    print(f"{label}: {len(p)} passed, {len(f)} failed, {len(s)} skipped "
          f"({len(outcomes)} collected)")
    if verbose:
        for o in f:
            print(f"  FAIL {o.id}")
            for line in o.reason.strip().splitlines()[-4:]:
                print(f"       {line}")
        for o in s:
            print(f"  SKIP {o.id}  — {o.reason}")
    return {"file": label, "error": False, "passed": len(p),
            "failed": len(f), "skipped": len(s), "collected": len(outcomes)}


# --------------------------------------------------------------------------
# 探針自驗：一組**事先寫死預期結果**的合成測試（含負面題）
# --------------------------------------------------------------------------

SELFTEST_SRC = '''
import os
import pytest

def test_plain_pass():
    assert 1 + 1 == 2

def test_plain_fail():
    assert 1 + 1 == 3

def test_raises_ok():
    with pytest.raises(ValueError):
        raise ValueError("x")

def test_raises_but_nothing_raised():
    with pytest.raises(ValueError):
        pass

def test_raises_wrong_type():
    with pytest.raises(ValueError):
        raise TypeError("y")

def test_raises_match_ok():
    with pytest.raises(ValueError, match="boom"):
        raise ValueError("a boom happened")

def test_raises_match_miss():
    with pytest.raises(ValueError, match="boom"):
        raise ValueError("nothing here")

def test_raises_as_value():
    with pytest.raises(ValueError) as ei:
        raise ValueError("payload")
    assert "payload" in str(ei.value)

def test_approx_ok():
    assert 0.1 + 0.2 == pytest.approx(0.3)

def test_approx_fail():
    assert 0.1 + 0.2 == pytest.approx(0.31)

def test_approx_rel_tight_fail():
    assert 1.0 == pytest.approx(1.0 + 1e-3, rel=1e-9)

def test_approx_abs_ok():
    assert 1.0 == pytest.approx(1.03, abs=0.04)

def test_approx_abs_fail():
    assert 1.0 == pytest.approx(1.05, abs=0.04)

@pytest.mark.parametrize("n", [1, 2, 3])
def test_param_three(n):
    assert n < 4

@pytest.mark.parametrize("n", [1, 2, 3])
def test_param_one_fails(n):
    assert n != 2

@pytest.mark.parametrize("a", [0, 1])
@pytest.mark.parametrize("b", [10, 20, 30])
def test_param_product(a, b):
    assert a + b > 0

@pytest.mark.parametrize("x,y", [(1, 2), (3, 4)])
def test_param_two_names(x, y):
    assert y > x

@pytest.mark.skipif(True, reason="故意跳過")
def test_skipif_true():
    raise AssertionError("skipif(True) 竟然執行了")

@pytest.mark.skipif(False, reason="不該跳")
def test_skipif_false():
    assert True

def test_skip_call():
    pytest.skip("中途跳過")

def test_fail_call():
    pytest.fail("故意失敗")

def test_needs_unknown_fixture(no_such_fixture):
    assert True

def test_tmp_path_usable(tmp_path):
    (tmp_path / "a.txt").write_text("hi")
    assert (tmp_path / "a.txt").read_text() == "hi"

_SEEN = []

def test_tmp_path_distinct_a(tmp_path):
    _SEEN.append(str(tmp_path))
    assert True

def test_tmp_path_distinct_b(tmp_path):
    _SEEN.append(str(tmp_path))
    assert len(set(_SEEN)) == len(_SEEN) == 2

class _Holder:
    v = 1

def test_monkeypatch_applies(monkeypatch):
    monkeypatch.setattr(_Holder, "v", 99)
    assert _Holder.v == 99

def test_monkeypatch_was_undone():
    assert _Holder.v == 1

def test_monkeypatch_setattr_string(monkeypatch):
    import json
    monkeypatch.setattr("json.dumps", lambda *a, **k: "patched")
    assert json.dumps({"a": 1}) == "patched"

def test_monkeypatch_setattr_string_undone():
    import json
    assert json.dumps({"a": 1}) == '{"a": 1}'

def test_monkeypatch_setattr_string_nested(monkeypatch):
    import json
    monkeypatch.setattr("json.JSONEncoder.mt_probe", 1, raising=False)
    assert json.JSONEncoder.mt_probe == 1

def test_monkeypatch_setattr_string_nested_undone():
    import json
    assert not hasattr(json.JSONEncoder, "mt_probe")

def test_monkeypatch_setattr_string_missing_raises(monkeypatch):
    with pytest.raises(AttributeError):
        monkeypatch.setattr("json.no_such_function", lambda: None)

def test_monkeypatch_env(monkeypatch):
    monkeypatch.setenv("MINITEST_PROBE", "on")
    assert os.environ["MINITEST_PROBE"] == "on"
    monkeypatch.delenv("MINITEST_PROBE")
    assert "MINITEST_PROBE" not in os.environ

def test_monkeypatch_env_undone():
    assert "MINITEST_PROBE" not in os.environ

def test_capsys_captures(capsys):
    print("hello-out")
    cap = capsys.readouterr()
    assert cap.out.strip() == "hello-out"

@pytest.fixture
def base_number():
    return 7

@pytest.fixture
def derived_number(base_number):
    return base_number * 3

def test_user_fixture_chain(derived_number):
    assert derived_number == 21

class TestClassCollected:
    def test_method_pass(self):
        assert True

    def test_method_fail(self):
        assert False

    @pytest.mark.parametrize("k", [1, 2])
    def test_method_param(self, k):
        assert k > 0

    def test_method_tmp_path(self, tmp_path):
        assert tmp_path.exists()

class NotATestClass:
    def test_should_not_be_collected(self):
        raise AssertionError("不以 Test 開頭的 class 不該被收集")
'''

# 事先寫死的預期（**寫在跑之前**）：id → 預期 status
SELFTEST_EXPECT = {
    "test_plain_pass": "passed",
    "test_plain_fail": "failed",
    "test_raises_ok": "passed",
    "test_raises_but_nothing_raised": "failed",   # 負面題：沒 raise 必須算失敗
    "test_raises_wrong_type": "failed",           # 負面題：抓到別的例外
    "test_raises_match_ok": "passed",
    "test_raises_match_miss": "failed",           # 負面題：match 不符
    "test_raises_as_value": "passed",
    "test_approx_ok": "passed",
    "test_approx_fail": "failed",                 # 負面題
    "test_approx_rel_tight_fail": "failed",       # 負面題：rel 收緊要抓得到
    "test_approx_abs_ok": "passed",
    "test_approx_abs_fail": "failed",             # 負面題
    "test_param_three[n=1]": "passed",
    "test_param_three[n=2]": "passed",
    "test_param_three[n=3]": "passed",
    "test_param_one_fails[n=1]": "passed",
    "test_param_one_fails[n=2]": "failed",        # 展開後只有這一格該失敗
    "test_param_one_fails[n=3]": "passed",
    "test_param_product[a=0,b=10]": "passed",
    "test_param_product[a=0,b=20]": "passed",
    "test_param_product[a=0,b=30]": "passed",
    "test_param_product[a=1,b=10]": "passed",
    "test_param_product[a=1,b=20]": "passed",
    "test_param_product[a=1,b=30]": "passed",
    "test_param_two_names[x=1,y=2]": "passed",
    "test_param_two_names[x=3,y=4]": "passed",
    "test_skipif_true": "skipped",                # 負面題：不准算 passed
    "test_skipif_false": "passed",
    "test_skip_call": "skipped",
    "test_fail_call": "failed",
    "test_needs_unknown_fixture": "skipped",      # 負面題：不准算 passed
    "test_tmp_path_usable": "passed",
    "test_tmp_path_distinct_a": "passed",
    "test_tmp_path_distinct_b": "passed",
    "test_monkeypatch_applies": "passed",
    "test_monkeypatch_was_undone": "passed",      # 負面題：沒還原就會失敗
    "test_monkeypatch_setattr_string": "passed",
    "test_monkeypatch_setattr_string_undone": "passed",   # 負面題：沒還原就失敗
    "test_monkeypatch_setattr_string_nested": "passed",   # mod.Class.attr 走 getattr
    "test_monkeypatch_setattr_string_nested_undone": "passed",
    "test_monkeypatch_setattr_string_missing_raises": "passed",
    "test_monkeypatch_env": "passed",
    "test_monkeypatch_env_undone": "passed",
    "test_capsys_captures": "passed",
    "test_user_fixture_chain": "passed",
    "TestClassCollected::test_method_pass": "passed",
    "TestClassCollected::test_method_fail": "failed",
    "TestClassCollected::test_method_param[k=1]": "passed",
    "TestClassCollected::test_method_param[k=2]": "passed",
    "TestClassCollected::test_method_tmp_path": "passed",
}

BADIMPORT_SRC = "import pytest\nraise RuntimeError('import 就炸')\n"
UNSUPPORTED_SRC = (
    "import pytest\n"
    "@pytest.mark.no_such_mark\n"
    "def test_x():\n    assert True\n"
)


def selftest(verbose=True):
    """探針先驗。回傳 True/False。**錯一條就不准拿去量未知的。**"""
    ok = True
    tmp = Path(tempfile.mkdtemp(prefix="minitest-self-"))
    try:
        f = tmp / "selftest_cases.py"
        f.write_text(SELFTEST_SRC, encoding="utf-8")
        outcomes, err = run_file(f)
        if err:
            print("SELFTEST: 合成測試檔本身 import 失敗\n" + err)
            return False
        got = {o.id: o.status for o in outcomes}
        missing = sorted(set(SELFTEST_EXPECT) - set(got))
        extra = sorted(set(got) - set(SELFTEST_EXPECT))
        mismatch = sorted(k for k in SELFTEST_EXPECT
                          if k in got and got[k] != SELFTEST_EXPECT[k])
        for k in missing:
            print(f"  SELFTEST 少收集：{k}（預期 {SELFTEST_EXPECT[k]}）")
        for k in extra:
            print(f"  SELFTEST 多收集：{k}（不該存在，status={got[k]}）")
        for k in mismatch:
            print(f"  SELFTEST 判錯：{k} 預期 {SELFTEST_EXPECT[k]}、實得 {got[k]}")
        ok = not (missing or extra or mismatch)
        n_exp = len(SELFTEST_EXPECT)
        print(f"SELFTEST 合成測試：{len(got)}/{n_exp} 條逐條相符"
              f" — {'OK' if ok else 'MISMATCH'}")

        # fail-closed 兩題：import 炸 ＝ ERROR、未實作的 mark ＝ ERROR（不是靜默通過）
        for label, src, want in (("badimport", BADIMPORT_SRC, "RuntimeError"),
                                 ("unsupported_mark", UNSUPPORTED_SRC,
                                  "no_such_mark")):
            g = tmp / f"selftest_{label}.py"
            g.write_text(src, encoding="utf-8")
            outs, e = run_file(g)
            good = bool(e) and want in e and not outs
            print(f"SELFTEST fail-closed[{label}]："
                  f"{'ERROR 且列名 — OK' if good else '沒擋住 — MISMATCH'}")
            ok = ok and good
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return ok


# --------------------------------------------------------------------------

def main(argv):
    selftest_only = "--selftest-only" in argv or "--selftest" in argv
    quiet = "--quiet" in argv
    files = [a for a in argv if not a.startswith("-")]

    install_stub_pytest()
    if str(REPO) not in sys.path:
        sys.path.insert(0, str(REPO))

    print("=" * 72)
    print("探針先驗（每次執行都跑；不過就不量未知的）")
    print("=" * 72)
    probe_ok = selftest()
    if not probe_ok:
        print("\n探針自驗失敗 ⇒ 不執行真的測試。exit 1")
        return 1
    if selftest_only:
        print("\n探針自驗全過（--selftest-only，未執行 tests/）。")
        return 0

    if not files:
        files = sorted(str(p) for p in (REPO / "tests").glob("test_*.py"))

    print("\n" + "=" * 72)
    print(f"執行 {len(files)} 個測試檔")
    print("=" * 72)
    rows = [report(f, *run_file(f), verbose=not quiet) for f in files]

    tp = sum(r["passed"] for r in rows)
    tf = sum(r["failed"] for r in rows)
    ts = sum(r["skipped"] for r in rows)
    errs = [r["file"] for r in rows if r["error"]]
    clean = [r for r in rows if not r["error"] and r["failed"] == 0]
    print("\n" + "=" * 72)
    print(f"總計：{tp} passed, {tf} failed, {ts} skipped"
          f"（{sum(r['collected'] for r in rows)} collected）")
    print(f"檔案：{len(rows)} 個，其中 0 failed 的 {len(clean)} 個、"
          f"有 failed 的 {len(rows) - len(clean) - len(errs)} 個、"
          f"import/收集 ERROR 的 {len(errs)} 個")
    if errs:
        print("ERROR 檔案（逐一列名，沒驗到就是沒驗到）：")
        for e in errs:
            print(f"  - {e}")
    print("提醒：minitest 不是 pytest；在這裡通過 ≠ 在 pytest 下通過。"
          "SKIP 一律不併進 passed。")
    return 0 if (tf == 0 and not errs) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
