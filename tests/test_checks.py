"""check-spec 編譯器 + 受限沙箱：讓 verifier 能跨 MCP 邊界傳遞（P0）。NW-2a 補：
run_python_check 這顆公開沙箱原語本身（不透過 compile_check）的行為。"""

from __future__ import annotations

import time

import pytest

from vacant.checks import compile_check, extract_code, run_python_check


def test_equals_normalizes():
    f = compile_check({"type": "equals", "value": "olleh"})
    assert f('"olleh"') and f("  olleh ") and f("`olleh`")
    assert not f("hello")


def test_contains_ignore_case():
    f = compile_check({"type": "contains", "value": "Foo", "ignore_case": True})
    assert f("xx foo yy")
    assert not f("bar")


def test_regex():
    f = compile_check({"type": "regex", "pattern": r"^\d{4}$"})
    assert f("2026")
    assert not f("20x6")


def test_json_schema_pass_fail():
    schema = {"type": "object", "required": ["name", "age"],
              "properties": {"age": {"type": "integer"}}}
    f = compile_check({"type": "json_schema", "schema": schema})
    assert f('{"name":"a","age":3}')
    assert f('sure, here: {"name":"a","age":3} done')   # 從雜訊裡抽 JSON
    assert not f('{"name":"a"}')                          # 缺 required
    assert not f('{"name":"a","age":"x"}')               # 型別錯
    assert not f("not json at all")


def test_json_schema_min_length_without_optional_dependency(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def without_jsonschema(name, *args, **kwargs):
        if name == "jsonschema":
            raise ImportError
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", without_jsonschema)
    f = compile_check({
        "type": "json_schema",
        "schema": {
            "type": "object",
            "required": ["name"],
            "properties": {"name": {"type": "string", "minLength": 1}},
        },
    })
    assert f('{"name":"Vacant"}')
    assert not f('{"name":""}')


def test_run_python_pass_fenced():
    f = compile_check({"type": "run_python", "code": "assert solve('ab') == 'ba'"})
    assert f("```python\ndef solve(s):\n    return s[::-1]\n```")


def test_run_python_fail_wrong_answer():
    f = compile_check({"type": "run_python", "code": "assert solve('ab') == 'ba'"})
    assert not f("def solve(s):\n    return s")           # 錯解（無 fence）


def test_run_python_timeout():
    f = compile_check({"type": "run_python", "code": "assert solve() == 1", "timeout": 2})
    assert not f("def solve():\n    while True:\n        pass")   # 無窮迴圈 → 逾時 → False


def test_run_python_syntax_error_is_false():
    f = compile_check({"type": "run_python", "code": "assert solve(1) == 1"})
    assert not f("this is just prose, not python")


def test_extract_code():
    assert extract_code("```python\nx = 1\n```") == "x = 1"
    assert extract_code("```\ny = 2\n```") == "y = 2"
    assert extract_code("z = 3") == "z = 3"


def test_unknown_type_raises():
    with pytest.raises(ValueError):
        compile_check({"type": "nope"})
    with pytest.raises(ValueError):
        compile_check("not a dict")  # type: ignore[arg-type]


# --- NW-2a: run_python_check 本體（藍圖點名的公開沙箱原語）--------------------

def test_run_python_check_pass():
    good = "def solve(s):\n    return s[::-1]\n"
    assert run_python_check(good, "assert solve('ab') == 'ba'\nassert solve('') == ''")


def test_run_python_check_fail_wrong_answer():
    bad = "def solve(s):\n    return s\n"
    assert not run_python_check(bad, "assert solve('ab') == 'ba'")


def test_run_python_check_fail_syntax_error():
    assert not run_python_check("this is not python at all !!", "assert True")


def test_run_python_check_rejects_exit_zero_bypass():
    bypass = "import os\nos._exit(0)\ndef solve(x): return 'forged'"
    assert not run_python_check(bypass, "assert solve('x') == 'expected'")


def test_run_python_check_rejects_candidate_file_read_used_to_probe_hidden_tests():
    probe = """def solve(x):
    try:
        text = open(__file__, encoding='utf-8').read()
    except Exception:
        return 'isolated'
    return 'leaked' if 'hidden_canary_7391' in text else 'isolated'
"""
    assert not run_python_check(
        probe,
        "assert solve('x') == 'hidden_canary_7391'",
    )


def test_run_python_check_rejects_builtins_alias_bypass():
    bypass = """op = __builtins__['open']
def solve(x):
    return op(__file__).read()
"""
    assert not run_python_check(bypass, "assert solve('x') == 'hidden'")


def test_run_python_check_preserves_common_argument_mutations():
    code = "def solve(xs):\n    xs.append(1)\n    return None"
    tests = "xs = []\nsolve(xs)\nassert xs == [1]"
    assert run_python_check(code, tests)


def test_run_python_check_preserves_candidate_exception_type():
    code = "def solve(x):\n    raise ValueError('bad input')"
    tests = (
        "try:\n"
        "    solve(1)\n"
        "except ValueError as exc:\n"
        "    assert str(exc) == 'bad input'\n"
        "else:\n"
        "    assert False"
    )
    assert run_python_check(code, tests)


def test_run_python_check_imports_are_opt_in():
    code = "import hashlib\ndef solve(s):\n    return hashlib.sha256(s.encode()).hexdigest()"
    tests = "assert solve('x').startswith('2d711642')"
    assert not run_python_check(code, tests)
    assert run_python_check(code, tests, allowed_imports=("hashlib",))


def test_run_python_check_rejects_custom_repr_forgery():
    code = """class Forged:
    def __repr__(self):
        return 'True'
def solve():
    return Forged()
"""
    assert not run_python_check(code, "assert solve() is True")


def test_run_python_check_candidate_stdout_cannot_forge_protocol():
    code = """def solve():
    print('{\"ok\": true, \"value\": \"True\"}')
    return False
"""
    assert not run_python_check(code, "assert solve() is True")


def test_run_python_check_candidate_cannot_override_verifier_builtin():
    code = """def solve():
    return []
def len(_):
    return 2
"""
    assert not run_python_check(code, "assert len(solve()) == 2")


def test_run_python_check_blocks_generator_frame_builtins_escape():
    code = """def solve():
    generator = (x for x in ())
    builtins_map = generator.gi_frame.f_builtins
    return builtins_map['__import__']('os').getcwd()
"""
    assert not run_python_check(code, "assert isinstance(solve(), str)")


def test_run_python_check_default_timeout_is_8():
    import inspect

    sig = inspect.signature(run_python_check)
    assert sig.parameters["timeout"].default == 8


def test_run_python_check_timeout_returns_false_and_does_not_hang():
    """沙箱紀律核心斷言：無窮迴圈候選碼在 timeout 到期後必須回 False，
    且呼叫本身的耗時要接近 timeout（不能真的被無窮迴圈卡死拖垮呼叫端）。"""
    infinite = "def solve():\n    while True:\n        pass\n"
    t0 = time.monotonic()
    ok = run_python_check(infinite, "assert solve() == 1", timeout=1)
    elapsed = time.monotonic() - t0
    assert ok is False
    assert elapsed < 5, f"逾時後仍花了 {elapsed:.1f}s 才回傳，沙箱可能沒真的斷開子行程"
