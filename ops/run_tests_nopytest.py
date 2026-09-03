"""零依賴執行單一測試模組——vacant-dev 這台**沒有裝 pytest**（2026-09-03 round642 查證：
`python3 -c "import pytest"` ModuleNotFoundError，全機 find 不到）。

所以 `tests/` 底下那些測試在這台機器上其實從來沒被執行過，而 DECISION 檔會引用
它們當證據（例：R440R 的 P-C4 說「round440q 的單元測試已驗過機制」）。
這支提供一個最小 pytest 替身把它們真的跑起來。

用法：  python3 ops/run_tests_nopytest.py tests/test_gain_conform_arm.py

⚠ 能力邊界（不要當成 pytest 的替代品）：只支援「module 層級的 test_* 函式」
＋「無參數的 fixture，且每個測試最多吃那一個 fixture」。
不支援 parametrize、conftest、class-based、fixture 相依。撐不住的會 ERROR 出來，
不會安靜跳過——安靜跳過才是這支存在的理由的反面。"""
import sys, types, traceback, importlib, inspect

# 最小 pytest 替身：只提供這支測試用到的 fixture / skip
pt = types.ModuleType("pytest")
class Skipped(Exception): pass
def fixture(*a, **k):
    def deco(fn): fn._is_fixture = True; return fn
    return deco(a[0]) if a and callable(a[0]) else deco
pt.fixture = fixture
def skip(msg=""): raise Skipped(msg)
pt.skip = skip
sys.modules["pytest"] = pt
sys.path.insert(0, ".")

mod_path = sys.argv[1] if len(sys.argv) > 1 else "tests/test_gain_conform_arm.py"
mod_name = mod_path.replace("/", ".").removesuffix(".py")
T = importlib.import_module(mod_name)

# 找出模組裡的 fixture（被 @pytest.fixture 標記過的），無參數呼叫一次
fixtures = {n: getattr(T, n) for n in dir(T)
            if getattr(getattr(T, n), "_is_fixture", False)}
resolved = {}
for fname, fn in fixtures.items():
    try:
        resolved[fname] = fn()
    except Skipped as e:
        print(f"SKIP  (fixture {fname}): {e}")
        sys.exit(0)
tests = [n for n in dir(T) if n.startswith("test_")]
fails = 0
for name in sorted(tests):
    fn = getattr(T, name)
    params = list(inspect.signature(fn).parameters)
    missing = [p for p in params if p not in resolved]
    if missing:
        fails += 1
        print(f"ERROR {name}: 需要這支撐不住的 fixture {missing}（用真 pytest 跑）")
        continue
    try:
        fn(*[resolved[p] for p in params])
        print(f"PASS  {name}")
    except Skipped as e:
        print(f"SKIP  {name}: {e}")
    except Exception:
        fails += 1
        print(f"FAIL  {name}")
        traceback.print_exc(limit=3)
print(f"\n{mod_path}: {len(tests)-fails}/{len(tests)} passed")
sys.exit(1 if fails else 0)
