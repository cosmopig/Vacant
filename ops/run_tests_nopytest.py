"""零依賴執行測試模組——vacant-dev 這台**沒有裝 pytest**（2026-09-03 round642 查證：
`python3 -c "import pytest"` ModuleNotFoundError，全機 find 不到）。

所以 `tests/` 底下那些測試在這台機器上其實從來沒被執行過，而 DECISION 檔會引用
它們當證據（例：R440R 的 P-C4 說「round440q 的單元測試已驗過機制」）。
這支提供一個最小 pytest 替身把它們真的跑起來。

用法：  python3 ops/run_tests_nopytest.py [tests/test_x.py ...]
        不給參數＝跑 tests/test_gain_conform_arm.py（沿用 round642 的預設）

## round646 擴充（為什麼）

round642 版只支援「module 層級 test_* 函式 ＋ 無參數 fixture」，實測結果是
**在範圍內的 7 個模組裡，35 個測試因為替身撐不住而 ERROR、1 個模組收集到 0 個**——
也就是說「跑過了」其實只跑到一半。本版補上 `tmp_path` / `monkeypatch` /
`pytest.raises` / `parametrize` / class-based 收集。

## ⚠ 兩條安靜綠燈（round646 事前點名，已修）

1. **收集到 0 個測試**舊版印 `0/0 passed` 且 `exit 0`。`tests/test_teeth.py` 全是
   class-based ⇒ 舊版對它安靜給綠。本版收集數為 0 一律 `NOT_VERIFIED` 並 `exit 1`。
2. **SKIP 被算進分子**（舊版 `len(tests)-fails`）。本版 pass/skip/fail/error 分開報。

## 能力邊界（不要當成 pytest 的替代品）

不支援：fixture 相依（fixture 吃 fixture）、`yield` fixture 的 teardown 順序保證、
`autouse`、conftest.py、`pytest.ini` 設定、大部分 `mark`（除 parametrize
與 skip 之外一律當 no-op）。撐不住的會 **ERROR 出來，不會安靜跳過**——
安靜跳過才是這支存在的理由的反面。
"""
import sys, types, traceback, importlib, inspect, os, shutil, tempfile, pathlib, contextlib

# ── 最小 pytest 替身 ─────────────────────────────────────────────
pt = types.ModuleType("pytest")


class Skipped(Exception):
    pass


def fixture(*a, **k):
    def deco(fn):
        fn._is_fixture = True
        return fn
    return deco(a[0]) if a and callable(a[0]) else deco


pt.fixture = fixture
pt.skip = lambda msg="": (_ for _ in ()).throw(Skipped(msg))
pt.fail = lambda msg="": (_ for _ in ()).throw(AssertionError(msg))


class _Raises:
    """pytest.raises 的最小版：支援 `match=`（re.search，同 pytest 語意）與 .value。"""

    def __init__(self, exc, match=None):
        self.exc, self.match, self.value = exc, match, None

    def __enter__(self):
        return self

    def __exit__(self, et, ev, tb):
        if et is None:
            raise AssertionError(f"DID NOT RAISE {self.exc}")
        if not issubclass(et, self.exc):
            return False                      # 讓真正的例外往上冒，不要吞掉
        if self.match is not None:
            import re
            if not re.search(self.match, str(ev)):
                raise AssertionError(f"{ev!r} 不符合 match={self.match!r}")
        self.value = ev
        return True


pt.raises = _Raises


class _Mark:
    """只實作 parametrize；其餘 mark 一律 no-op 裝飾器（不改變測試行為）。"""

    def parametrize(self, argnames, argvalues, **kw):
        names = ([n.strip() for n in argnames.split(",")]
                 if isinstance(argnames, str) else list(argnames))

        def deco(fn):
            fn._parametrize = (names, list(argvalues))
            return fn
        return deco

    def __getattr__(self, _name):
        def deco(*a, **k):
            if a and callable(a[0]) and not k:
                return a[0]
            return lambda fn: fn
        return deco


class _Approx:
    """pytest.approx 的最小版（純量／序列）。預設 rel=1e-6, abs=1e-12，同 pytest。"""

    def __init__(self, expected, rel=None, abs=None):
        self.expected, self.rel, self.abs = expected, rel, abs

    def _close(self, a, b):
        rel = 1e-6 if self.rel is None else self.rel
        ab = 1e-12 if self.abs is None else self.abs
        try:
            return abs_builtin(a - b) <= max(ab, rel * abs_builtin(b))
        except TypeError:
            return a == b

    def __eq__(self, other):
        e = self.expected
        if isinstance(e, (list, tuple)):
            return (isinstance(other, (list, tuple)) and len(other) == len(e)
                    and all(self._close(x, y) for x, y in zip(other, e)))
        if isinstance(e, dict):
            return (isinstance(other, dict) and other.keys() == e.keys()
                    and all(self._close(other[k], e[k]) for k in e))
        return self._close(other, e)

    def __repr__(self):
        return f"approx({self.expected!r})"


abs_builtin = abs
pt.approx = _Approx
pt.mark = _Mark()
sys.modules["pytest"] = pt
sys.path.insert(0, ".")


# ── 內建 fixture ─────────────────────────────────────────────────
class _MonkeyPatch:
    def __init__(self):
        self._undo = []

    _MISSING = object()

    def setattr(self, target, name, value=_MISSING, raising=True):
        # 字串形式：monkeypatch.setattr("pkg.mod.attr", value) —— 只有兩個位置參數，
        # 第一個帶點路徑。tests/test_evalplus_loader.py 用的就是這個形式。
        if isinstance(target, str):
            # 字串形式只有兩個位置參數：setattr("pkg.mod.attr", value)
            # ⇒ 呼叫端傳進來的 `name` 其實是 value，`value` 必須還是空的。
            if value is not self._MISSING:
                raise TypeError("字串形式的 setattr 只吃兩個位置參數")
            mod_name, _, attr = target.rpartition(".")
            if not mod_name:
                raise ValueError(f"setattr 目標要帶模組路徑：{target!r}")
            target, name, value = importlib.import_module(mod_name), attr, name
        elif value is self._MISSING:
            raise TypeError("setattr 需要 value")
        had = hasattr(target, name)
        old = getattr(target, name, None)
        if raising and not had:
            raise AttributeError(f"{target!r} 沒有屬性 {name}")
        setattr(target, name, value)
        self._undo.append(lambda: setattr(target, name, old) if had
                          else delattr(target, name))

    def delattr(self, target, name, raising=True):
        if not hasattr(target, name):
            if raising:
                raise AttributeError(name)
            return
        old = getattr(target, name)
        delattr(target, name)
        self._undo.append(lambda: setattr(target, name, old))

    def setitem(self, dic, name, value):
        had, old = name in dic, dic.get(name)
        dic[name] = value
        self._undo.append(lambda: dic.__setitem__(name, old) if had
                          else dic.pop(name, None))

    def delitem(self, dic, name, raising=True):
        if name not in dic:
            if raising:
                raise KeyError(name)
            return
        old = dic.pop(name)
        self._undo.append(lambda: dic.__setitem__(name, old))

    def setenv(self, name, value, prepend=None):
        self.setitem(os.environ, name, str(value))

    def delenv(self, name, raising=True):
        self.delitem(os.environ, name, raising=raising)

    def syspath_prepend(self, path):
        sys.path.insert(0, str(path))
        self._undo.append(lambda: sys.path.remove(str(path)))

    def chdir(self, path):
        old = os.getcwd()
        os.chdir(str(path))
        self._undo.append(lambda: os.chdir(old))

    def undo(self):
        while self._undo:
            self._undo.pop()()


BUILTIN = {"tmp_path", "monkeypatch", "tmpdir"}


@contextlib.contextmanager
def _builtin_fixtures(names):
    """每個測試拿到全新的 tmp_path / monkeypatch，跑完拆掉（pytest 的 function scope）。"""
    made, tmpdir, mp = {}, None, None
    try:
        if "tmp_path" in names or "tmpdir" in names:
            tmpdir = tempfile.mkdtemp(prefix="nopytest-")
            made["tmp_path"] = made["tmpdir"] = pathlib.Path(tmpdir)
        if "monkeypatch" in names:
            mp = _MonkeyPatch()
            made["monkeypatch"] = mp
        yield made
    finally:
        if mp is not None:
            mp.undo()
        if tmpdir:
            shutil.rmtree(tmpdir, ignore_errors=True)


# ── 收集 ─────────────────────────────────────────────────────────
def collect(T):
    """回傳 [(顯示名, 可呼叫物)]；含 module 層級 test_* 與 class-based Test*。"""
    items = []

    def expand(name, fn, bind=None):
        call = (lambda *a, **k: fn(bind, *a, **k)) if bind is not None else fn
        call.__signature__ = inspect.signature(fn)
        params = [p for p in call.__signature__.parameters
                  if not (bind is not None and p == "self")]
        pm = getattr(fn, "_parametrize", None)
        if not pm:
            items.append((name, call, params))
            return
        pnames, pvals = pm
        for i, vals in enumerate(pvals):
            vals = vals if isinstance(vals, (tuple, list)) else (vals,)
            kw = dict(zip(pnames, vals))
            rest = [p for p in params if p not in kw]
            items.append((f"{name}[{i}]",
                          (lambda c=call, kw=kw: lambda *a: c(*a, **kw))(), rest))

    for n in sorted(dir(T)):
        obj = getattr(T, n)
        if n.startswith("test_") and callable(obj) and not isinstance(obj, type):
            expand(n, obj)
        elif n.startswith("Test") and isinstance(obj, type):
            inst = None
            for m in sorted(dir(obj)):
                if not m.startswith("test_"):
                    continue
                if inst is None:
                    try:
                        inst = obj()
                    except Exception:
                        items.append((f"{n}::<init>", None, ["<無法建構這個測試類別>"]))
                        break
                expand(f"{n}::{m}", getattr(obj, m), bind=inst)
    return items


def run_module(mod_path):
    mod_name = mod_path.replace("/", ".").removesuffix(".py")
    try:
        T = importlib.import_module(mod_name)
    except Exception:
        traceback.print_exc(limit=6)
        print(f"\n{mod_path}: IMPORT_ERROR")
        return {"pass": 0, "fail": 0, "error": 1, "skip": 0, "n": 0,
                "verdict": "IMPORT_ERROR"}

    # 模組自訂 fixture（被 @pytest.fixture 標記、且不吃參數）
    fixtures = {n: getattr(T, n) for n in dir(T)
                if getattr(getattr(T, n, None), "_is_fixture", False)}
    items = collect(T)
    tally = {"pass": 0, "fail": 0, "error": 0, "skip": 0, "n": len(items)}
    for name, fn, params in sorted(items):
        missing = [p for p in params
                   if p not in BUILTIN and p not in fixtures]
        if fn is None or missing:
            tally["error"] += 1
            print(f"ERROR {name}: 需要這支撐不住的 {missing}（用真 pytest 跑）")
            continue
        try:
            with _builtin_fixtures([p for p in params if p in BUILTIN]) as built:
                args = []
                for p in params:
                    args.append(built[p] if p in built else fixtures[p]())
                fn(*args)
            tally["pass"] += 1
            print(f"PASS  {name}")
        except Skipped as e:
            tally["skip"] += 1
            print(f"SKIP  {name}: {e}")
        except Exception:
            tally["fail"] += 1
            print(f"FAIL  {name}")
            traceback.print_exc(limit=4)

    if tally["n"] == 0:
        tally["verdict"] = "NOT_VERIFIED(收集到 0 個測試)"
    elif tally["fail"]:
        tally["verdict"] = "FAIL"
    elif tally["error"]:
        tally["verdict"] = "UNSUPPORTED"
    elif tally["skip"]:
        tally["verdict"] = "PASS_WITH_SKIP"
    else:
        tally["verdict"] = "PASS"
    print(f"\n{mod_path}: {tally['pass']}/{tally['n']} pass, "
          f"{tally['fail']} fail, {tally['error']} error, {tally['skip']} skip "
          f"=> {tally['verdict']}")
    return tally


if __name__ == "__main__":
    paths = sys.argv[1:] or ["tests/test_gain_conform_arm.py"]
    results = {}
    for p in paths:
        print(f"############ {p}")
        results[p] = run_module(p)
    if len(paths) > 1:
        print("\n==== 總表 ====")
        for p, t in results.items():
            print(f"{t['verdict']:26s} {t['pass']:3d}/{t['n']:<3d} "
                  f"fail={t['fail']} err={t['error']} skip={t['skip']}  {p}")
    # 收集到 0 個 / 有 fail / 有 error 一律非零退出：沒驗到不准印成綠的
    bad = sum(1 for t in results.values()
              if t["verdict"] not in ("PASS", "PASS_WITH_SKIP"))
    sys.exit(1 if bad else 0)
