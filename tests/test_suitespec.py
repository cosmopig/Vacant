"""suitespec 的確定性測試——「驗收套件是資料不是程式」這句話的可執行版本。

每一條對應 `vacant/suitespec.py` 的一句主張。分成四組：
  §1 validator：什麼進得來、什麼進不來（不可表達性就是靠這一組成立的）
  §2 正規化與確定性：上鏈的位元組是重寫過的、渲染是確定性的
  §3 與 loader 的一致：前置逐位元組相同；真題無損轉換（**真沙箱**）
  §4 R451 三種攻擊沒有編碼

⚠ §3 有兩條會跑本機沙箱（無損那一條的主張就是「真的跑起來標籤一樣」，
  用假 runner 測只會測到假 runner）。零模型呼叫、零 API、零 `runs/` 寫入。
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault(
    "VACANT_EVALPLUS_PATH", ".vacant-private/evalplus/MbppPlus-v0.2.0.jsonl.gz"
)

from vacant import suitespec as ss  # noqa: E402
from vacant.suitespec import SuiteSpecError  # noqa: E402


def spec(tests=None, **over):
    d = {"v": 1, "dialect": "mbpp", "entry_point": "f",
         "tests": tests if tests is not None else [{"args": "[1]", "expected": "2"}],
         "cmp": {"atol": None, "set_equivalent": False, "regex_predicate": False}}
    d.update(over)
    return ss.validate(d)


# ── 1. validator：不可表達性的來源 ──────────────────────────────────────────
@pytest.mark.parametrize("bad", [
    "f(1)",                       # 呼叫
    "open",                       # 名稱
    "os.path",                    # 屬性存取
    "lambda x: x",                # lambda
    "[x for x in range(3)]",      # 推導式
    "f'{x}'",                     # f-string
    "__import__('os')",           # import
    "1 if True else 2",           # 條件式
    "1e999",                      # 合法字面值但 parse 成 inf
    "[1e999]",                    # 巢狀 inf
    "set()",                      # 空集合不是字面值
    "{**{}}",                     # 解包
    "()" * 3,                     # 語法錯
])
def test_validator_rejects_everything_that_is_not_a_literal(bad):
    """`ast.literal_eval` ＋ 型別走訪：呼叫／名稱／屬性／lambda／推導式／f-string 全死。

    這一組**就是**「有狀態、雜湊黑名單、擬態三種攻擊不可表達」的機制來源：
    那三種攻擊都需要在套件裡放一段會執行的東西，而這裡連一個名稱都放不進去。
    """
    with pytest.raises(SuiteSpecError):
        ss.parse_literal(bad)


@pytest.mark.parametrize("good", [
    "None", "True", "1", "-3", "1.5", "'abc'", "b'xy'", "[1, [2, 3]]",
    "(1,)", "{'a': 1}", "{1, 2}", "(1+2j)",
])
def test_validator_accepts_plain_literals(good):
    """反方向：真的字面值要進得來，不然這道門只是把所有東西焊死。"""
    assert ss.canonical_literal(good)


def test_empty_suite_is_rejected():
    """0 條測資＝什麼都不驗＝R449 §三-3 那一格。連量具都不必跑，validator 先擋。"""
    with pytest.raises(SuiteSpecError) as e:
        spec(tests=[])
    assert "empty_suite_rejected" in str(e.value)


def test_a_raw_code_string_is_not_a_spec():
    """被拆掉的那道門：一段驗收 Python 遞進 validator 就是型別錯誤。"""
    with pytest.raises(SuiteSpecError) as e:
        ss.validate("assert f(1) == 2\n")
    assert "raw_code_suite_not_accepted" in str(e.value)


@pytest.mark.parametrize("ep,why", [
    ("__aeq", "entry_point_reserved"),          # 撞渲染器用掉的名字
    ("__canon", "entry_point_reserved"),
    ("_worker", "entry_point_reserved"),
    ("class", "entry_point_reserved"),          # 關鍵字
    ("not an identifier", "entry_point_not_identifier"),
    ("f(1)", "entry_point_not_identifier"),
])
def test_entry_point_is_constrained(ep, why):
    """entry_point 是要被寫進渲染碼的名字 ⇒ 撞名或不是識別字一律拒。"""
    with pytest.raises(SuiteSpecError) as e:
        spec(entry_point=ep)
    assert why in str(e.value)


def test_args_must_be_positional():
    """`args` 是一串位置引數 ⇒ 必須是列表／元組字面值。"""
    with pytest.raises(SuiteSpecError) as e:
        spec(tests=[{"args": "1", "expected": "2"}])
    assert "args_not_positional" in str(e.value)


def test_unknown_keys_are_rejected_in_tests_and_cmp():
    """多出來的鍵一律拒：一個被忽略的欄位＝一個 spec 說了但沒人執行的東西。"""
    with pytest.raises(SuiteSpecError):
        spec(tests=[{"args": "[1]", "expected": "2", "timeout": "9"}])
    with pytest.raises(SuiteSpecError):
        spec(cmp={"atol": None, "shell": True})


def test_lcb_dialect_has_no_comparator_knobs():
    """lcb 的比較器寫死在前置裡（1e-6＋bool 守衛）⇒ cmp 三欄必須是未使用值。

    這條同時是一句誠實話：**旗標放寬那一類攻擊在 lcb 方言上不可表達**
    ——不是被擋，是沒有那個旋鈕。
    """
    ok = ss.validate({"v": 1, "dialect": "lcb", "entry_point": "f",
                      "tests": [{"args": "[1]", "expected": "2"}], "cmp": {}})
    assert ok.dialect == "lcb" and ok.atol is None
    with pytest.raises(SuiteSpecError) as e:
        ss.validate({"v": 1, "dialect": "lcb", "entry_point": "f",
                     "tests": [{"args": "[1]", "expected": "2"}],
                     "cmp": {"atol": 1e9}})
    assert "lcb_dialect_has_no_cmp_knobs" in str(e.value)


def test_caps_are_enforced():
    """尺寸有界：沒有界的話「一份 spec」可以是一顆記憶體炸彈。"""
    with pytest.raises(SuiteSpecError) as e:
        spec(tests=[{"args": "[1]", "expected": "2"}] * (ss.MAX_TESTS + 1))
    assert "too_many_tests" in str(e.value)
    with pytest.raises(SuiteSpecError) as e:
        ss.parse_literal("'" + "a" * (ss.MAX_LITERAL_CHARS + 1) + "'")
    assert "literal_too_long" in str(e.value)
    deep = "[" * (ss.MAX_DEPTH + 2) + "]" * (ss.MAX_DEPTH + 2)
    with pytest.raises(SuiteSpecError):
        ss.parse_literal(deep)


def test_bad_version_and_dialect_are_rejected():
    with pytest.raises(SuiteSpecError):
        spec(v=2)
    with pytest.raises(SuiteSpecError):
        spec(dialect="mbpp2")


# ── 2. 正規化與確定性 ──────────────────────────────────────────────────────
def test_literals_are_re_emitted_not_copied():
    """**上鏈的位元組是重寫過的**，不是作者排版過的：同一個值只有一種寫法。"""
    a = spec(tests=[{"args": "[  1 ,  2 ]", "expected": "{'b':2,'a':1}"}])
    b = spec(tests=[{"args": "[1,2]", "expected": "{'b': 2, 'a': 1}"}])
    assert a.tests[0].args == "[1, 2]"
    assert a.suite_sha256 == b.suite_sha256
    # 元組／單元素元組／巢狀也要正規
    assert ss.canonical_literal("( 1 , )") == "(1,)"
    assert ss.canonical_literal("[(1,2),[3]]") == "[(1, 2), [3]]"


def test_sets_are_emitted_in_a_hash_independent_order():
    """集合的 `repr` 順序跟著 PYTHONHASHSEED 走 ⇒ 一定要自己排序，否則跨機 hash 不同。

    這條不是潔癖：`suite_sha256` 跨機不一致的話，「第三方可重算」直接失效。
    """
    assert ss.canonical_literal("{'b', 'a', 'c'}") == ss.canonical_literal("{'c', 'b', 'a'}")
    import subprocess
    import sys
    prog = ("import sys; sys.path.insert(0, '.');"
            "from vacant.suitespec import canonical_literal;"
            "print(canonical_literal(\"{'b', 'a', 'c', 'zz', 'q'}\"))")
    outs = set()
    for seed in ("0", "1", "12345"):
        env = dict(os.environ, PYTHONHASHSEED=seed)
        outs.add(subprocess.run([sys.executable, "-c", prog], capture_output=True,
                                text=True, env=env, check=True).stdout.strip())
    assert len(outs) == 1, outs


def test_render_is_deterministic_and_hash_binds_data_not_code():
    """同一份 spec ⇒ 同一份碼；`suite_sha256` 算在**資料**上，不是算在碼上。"""
    s1, s2 = spec(), spec()
    assert s1.render() == s2.render()
    assert s1.suite_sha256 == s2.suite_sha256
    import hashlib
    assert s1.suite_sha256 != hashlib.sha256(s1.render().encode()).hexdigest()
    assert s1.suite_sha256 == hashlib.sha256(s1.canonical_bytes()).hexdigest()
    # canonical bytes 進得來、出得去（第三方拿 bytes 就能重建同一份 spec）
    assert ss.validate(s1.canonical_bytes()).suite_sha256 == s1.suite_sha256


def test_render_puts_no_supplier_bytes_into_executable_positions():
    """渲染出來的碼只有三種行：固定前置、一行 entry 綁定、一串 assert。

    round452b：entry point **不再是裸名字**。它只以 repr 過的字串鍵出現在
    `__vacant_ns[...]` 裡，所以 assert 那一行裡的自由 token 全是渲染器自己的名字
    （`__aeq`／`__entry`）——供應者給的每一個位元組都在字面值的位置上。
    """
    s = spec(tests=[{"args": "[1, 2]", "expected": "'x'"}])
    code = s.render()
    body = [ln for ln in code.splitlines() if ln.startswith("assert ")]
    assert body == ["assert __aeq(__entry(*[1, 2]), 'x', None)"]
    assert code.startswith("import re as __vacant_re\n")
    assert "__entry = __vacant_ns['f']" in code.splitlines()


# ── 3. 與 loader 一致（前置逐位元組；真題無損）──────────────────────────────
def test_preludes_are_byte_identical_to_the_loaders():
    """反漂移：`suitespec` 的前置必須與 `codebench` 產生的**逐位元組相同**。

    兩份實作不共用一段字串是刻意的（機制層不相依題庫載入器），所以漂移防呆
    要有人吵——就是這一條。四種旗標組合都比。
    """
    from vacant.codebench import _check_code, _lcb_check_code
    for rxp in (False, True):
        for seq in (False, True):
            canon = ("import re\ndef g(x):\n    return re.search('a', x)\n" if rxp
                     else "def g(x):\n    return x\n")
            ep = "similar_elements" if seq else "g"
            gen = _check_code(ep, canon, [], None)
            head = gen[:gen.index("__ns: dict = {}")]
            assert head == ss.mbpp_prelude(rxp, seq), (rxp, seq)
    gen = _lcb_check_code("g", [{"args": [1], "expected": 2}])
    assert gen[:gen.index("__tests = ")] == ss.lcb_prelude()


def test_lcb_conversion_differs_from_the_loader_by_exactly_the_entry_binding():
    """LCB 轉換的無損性：與 loader 的碼**只差 entry point 怎麼取**，一個位元組不多。

    ⚠ round452b 之前這一條是「逐位元組相同」。修法（`entry_binding`：改成
      `__entry = __vacant_ns['名字']`）把那個性質**弄掉了**，這裡照實記下代價，
      不假裝還在：loader 自己仍然用裸名字呼叫受測函式，而 loader 的碼不是供應者
      寫的（entry point 來自題庫），所以那一側不是本次修的破口。

    退回去的方式寫成可執行的：把綁定那一行拿掉、把 `__entry(` 換回原名，就必須
    與 loader 的碼逐位元組相同。這比舊版更嚴——它同時釘住「差別只有這一處」。
    """
    from vacant.codebench import LiveCodeBenchLoader
    tasks = list(LiveCodeBenchLoader().iter_tasks("x"))
    assert len(tasks) == 91
    for t in tasks[:12]:
        conv = ss.from_task(t)
        assert conv.spec is not None, (t["task_id"], conv.reason)
        ep = conv.spec.entry_point
        bind = ss.entry_binding(ep)
        rendered = conv.spec.render()
        assert bind in rendered.splitlines()
        undone = "\n".join(ln for ln in rendered.splitlines() if ln != bind)
        assert undone.replace("__entry(", ep + "(") == t["visible_check"]["code"]


@pytest.fixture(scope="module")
def mbpp_tasks():
    from vacant.codebench import EvalPlusMBPPLoader
    try:
        return list(EvalPlusMBPPLoader(expose_contract=True).iter_tasks("x"))
    except FileNotFoundError:
        pytest.skip("EvalPlus 官方包不在本機（VM 上才有），跳過")


def test_lossless_on_real_mbpp_tasks_in_the_real_sandbox(mbpp_tasks):
    """**無損的定義**：渲染後的套件在真沙箱上給出的標籤，與 loader 的套件逐格相同。

    三題、每題四個受測體（參考解／三種壞樁）＝24 次真沙箱。全量版本是
    `ops/gain/replay/r452_suitespec.py --census`（1855＋455 個真候選，
    結果落在 `cache/r452_census_*.json`）。
    """
    from ops.gain.gain_run import meets_demand
    picked = [t for t in mbpp_tasks
              if t["entry_point"] in ("similar_elements", "is_not_prime", "heap_queue_largest")]
    assert len(picked) == 3
    for t in picked:
        ep = t["entry_point"]
        conv = ss.from_task(t)
        assert conv.spec is not None, (t["task_id"], conv.reason)
        rendered, loader_code = conv.spec.render(), t["visible_check"]["code"]
        assert rendered != loader_code                       # 參考解那段不見了
        subjects = [conv.reference,
                    f"def {ep}(*a, **k):\n    return None\n",
                    f"def {ep}(*a, **k):\n    return []\n",
                    f"def {ep}(*a, **k):\n    return a[0] if a else None\n"]
        for src in subjects:
            assert (meets_demand(src, rendered, 10, entry_point=ep)[0]
                    == meets_demand(src, loader_code, 10, entry_point=ep)[0]), (t["task_id"], src[:40])


def test_unconvertible_tasks_are_reported_not_fudged(mbpp_tasks):
    """轉不了就說轉不了：參考解回傳 `re.Match` 的題目沒有字面值可以放。

    三題（Mbpp/737、787、794）是**真實的**轉換成本，不是四捨五入掉的誤差。
    """
    by_id = {t["task_id"]: t for t in mbpp_tasks}
    t = by_id.get("mbppplus_Mbpp/737")
    if t is None:
        pytest.skip("題庫版本沒有這題")
    conv = ss.from_task(t)
    assert conv.spec is None
    assert conv.reason.startswith("expected_not_a_literal_type:Match")


# ── 4. R451 三種攻擊：沒有編碼 ──────────────────────────────────────────────
def test_r451_attack_suites_have_no_encoding(mbpp_tasks):
    """targeted（雜湊黑名單）／mimic（換掉受測函式）／stateful（跨呼叫狀態）／
    trivial（`pass`）四份驗收碼，餵進 `parse_check_code` 一律被拒。

    「不可表達」是型別性質不是宣稱：這四段碼都需要在套件裡放一段會執行的東西
    （`import`、`open`、`hashlib`、`exec`），而 `SuiteSpec` 的欄位只有 entry_point、
    一串字面值、三個比對旗標。
    """
    from ops.gain.replay.peer_exec_sim import mimic_suite, targeted_suite
    from ops.gain.replay.r451_stateful_suite_probe import stateful_suite

    t = next(x for x in mbpp_tasks if x["entry_point"] == "similar_elements")
    ep, real = t["entry_point"], t["visible_check"]["code"]
    # 先確認**真的**那一套認得出來（不是把所有輸入都拒掉）
    assert ss.parse_check_code(real)["entry_point"] == ep
    for name, code in (("targeted", targeted_suite(ep)),
                       ("mimic", mimic_suite(real, ep)),
                       ("stateful", stateful_suite(real, ep)),
                       ("trivial", "pass")):
        if code is None:          # mimic 認不出形狀就造不出來——那也是「不可表達」
            continue
        with pytest.raises(SuiteSpecError) as e:
            ss.parse_check_code(code)
        assert "unrecognized_suite_shape" in str(e.value), (name, str(e.value))
        with pytest.raises(SuiteSpecError):
            ss.validate(code)


def test_a_spec_cannot_smuggle_code_through_the_expected_field():
    """把攻擊碼塞進 `expected` 也沒有用：它必須先是字面值，然後被重寫成字串。

    `"__import__('os').system('x')"` 這種東西進不了 `expected`；就算把它寫成
    **字串字面值**，渲染出來也只是一個被比較的字串常數，不是可執行的東西。
    """
    with pytest.raises(SuiteSpecError):
        spec(tests=[{"args": "[1]", "expected": "__import__('os')"}])
    smuggled = spec(tests=[{"args": "[1]", "expected": "\"__import__('os')\""}])
    line = [ln for ln in smuggled.render().splitlines() if ln.startswith("assert ")][0]
    assert line == 'assert __aeq(__entry(*[1]), "__import__(\'os\')", None)'


def test_a_zero_test_spec_is_refused_by_the_validator_and_by_the_gauge():
    """兩道門都要關：validator 拒絕 `tests=[]`，而**萬一**繞過 validator，量具也擋。

    第二半是真沙箱：直接建一個繞過 `validate` 的 `SuiteSpec`（dataclass 建構子），
    渲染出來只剩前置、零條 assert ⇒ 參考解通過、壞樁也通過 ⇒ `all_rejected=False`
    ⇒ 量具不合格。fail-open 要兩層都堵，因為「validator 有一天被改鬆」不是不可能。
    """
    from vacant.suitegauge import broken_stub, gauge_suite

    with pytest.raises(SuiteSpecError):
        spec(tests=[])
    # `render` 只對**非** SuiteSpec 的輸入跑 validate；直接建構的 dataclass 會被
    # 原樣渲染，渲染出來就是「零條 assert」的那份碼——正好用來測第二道門。
    naked = ss.SuiteSpec(entry_point="f", tests=(), dialect="mbpp")
    code = ss.render(naked)
    assert "assert " not in code
    ref = "def f(x):\n    return x + 1\n"
    out = gauge_suite(code, ref, [broken_stub("f")], entry_point="f")
    assert out.ref_passed and not out.all_rejected and not out.ok
    # 而且 peerexec 那條路根本走不到這裡：它先 validate。
    from vacant.peerexec import run_suite_gauge
    with pytest.raises(SuiteSpecError) as e:
        run_suite_gauge(naked, ref, [broken_stub("f")], entry_point="f")
    assert "empty_suite_rejected" in str(e.value)


# ── 5. round452b：entry point 走私 ─────────────────────────────────────────
#
# 這一組是一次**已經發生過的**破口的回歸測試，不是假想。1cfec80 上 `entry_point`
# 是套件的欄位、渲染器把它當裸名字寫進碼裡，於是 `entry_point="exec"` ＋
# 一條 `args=["<任意 Python>"]` 就是一次任意程式執行（實測假交付 31.52%，
# `ops/gain/replay/r452b_smuggle_gate.py`）。

def test_entry_point_must_match_the_task():
    """entry_point 屬於**題目**：`validate(..., entry_point=題目的)` 不符即拒。"""
    assert spec().entry_point == "f"
    assert ss.validate({"v": 1, "dialect": "mbpp", "entry_point": "f",
                        "tests": [{"args": "[1]", "expected": "2"}], "cmp": {}},
                       entry_point="f").entry_point == "f"
    with pytest.raises(SuiteSpecError) as e:
        ss.validate({"v": 1, "dialect": "mbpp", "entry_point": "g",
                     "tests": [{"args": "[1]", "expected": "2"}], "cmp": {}},
                    entry_point="f")
    assert str(e.value) == "entry_point_mismatch"
    # 題目沒宣告 entry point（空字串／別的型別）⇒ 沒有東西可以綁 ⇒ 拒。
    for absent in ("", 0, [], "F"):
        with pytest.raises(SuiteSpecError) as e2:
            ss.validate({"v": 1, "dialect": "mbpp", "entry_point": "f",
                         "tests": [{"args": "[1]", "expected": "2"}], "cmp": {}},
                        entry_point=absent)
        assert str(e2.value) == "entry_point_mismatch"


@pytest.mark.parametrize("ep", ["exec", "eval", "open", "getattr", "os", "subprocess",
                                "compile", "__import__", "globals", "setattr",
                                "_worker", "_vacant_call", "__vacant_ns"])
def test_dangerous_entry_points_are_refused_even_when_the_task_asks_for_them(ep):
    """一題的 entry_point 是 `exec`，**這題自己**就被拒——沒有「題目說了算」的例外。

    ⚠ 這層是**防禦縱深**不是修法：修法是 `entry_binding` 的命名空間查找
      （下一條測的），它讓這些名字在結構上就到不了 builtins。兩層都要在，
      因為「結構上到不了」這句話依賴 `vacant/checks.py` 的模板，而兩個檔案會各自演化。
    """
    with pytest.raises(SuiteSpecError) as e:
        ss.validate({"v": 1, "dialect": "mbpp", "entry_point": ep,
                     "tests": [{"args": "['x']", "expected": "None"}], "cmp": {}},
                    entry_point=ep)
    assert str(e.value) == "entry_point_reserved"


def test_a_task_may_still_own_a_pure_value_builtin_name():
    """反方向：`sum` 是真的 MBPP+ 題目（Mbpp/126）的 entry point，不准被誤殺。

    黑名單是 default-deny ＋ 一小張釘死的純取值白名單（`TASK_OWNABLE_BUILTINS`）。
    整個 `dir(builtins)` 一刀切會擋掉一題**合法的題目**——那會讓一層防禦縱深變成
    功能退化，而它明明不是修法本身。
    """
    s = ss.validate({"v": 1, "dialect": "mbpp", "entry_point": "sum",
                     "tests": [{"args": "[[1, 2]]", "expected": "3"}], "cmp": {}},
                    entry_point="sum")
    assert s.entry_point == "sum"
    assert "__entry = __vacant_ns['sum']" in s.render().splitlines()
    assert ss.TASK_OWNABLE_BUILTINS <= frozenset(dir(__import__("builtins")))
    for danger in ("exec", "eval", "open", "getattr", "compile", "__import__"):
        assert danger not in ss.TASK_OWNABLE_BUILTINS


def test_entry_point_blacklist_covers_the_runner_template():
    """漂移防呆：runner 模板在 module scope 綁的每一個名字都要在黑名單裡。

    `vacant/checks.py::_test_runner_source` 是**另一個檔案**。它哪天多 import 一個
    模組，這條就會 FAIL——而不是安靜地多出一個可以被 entry_point 撞到的名字。
    """
    import ast as _ast

    from vacant.checks import _test_runner_source
    src = _test_runner_source(worker_path="/w.py", candidate_path="/c.py",
                              worker_cwd="/tmp", nonce="N:", call_timeout=1.0,
                              test_code="pass", function_names=[])
    bound: set[str] = set()

    def walk_module_scope(nodes):
        # 只看 **module scope**：函式／類別內部的區域名字撞不到 entry point，
        # 把它們算進來只會讓這條防呆變成雜訊。
        for node in nodes:
            if isinstance(node, (_ast.Import, _ast.ImportFrom)):
                bound.update((a.asname or a.name).split(".")[0] for a in node.names)
            elif isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef,
                                   _ast.ClassDef)):
                bound.add(node.name)
                continue
            for child in _ast.iter_child_nodes(node):
                if isinstance(child, _ast.Name) and isinstance(child.ctx, _ast.Store):
                    bound.add(child.id)
                elif isinstance(child, (_ast.Tuple, _ast.List)):
                    bound.update(e.id for e in child.elts
                                 if isinstance(e, _ast.Name)
                                 and isinstance(e.ctx, _ast.Store))
            walk_module_scope([c for c in _ast.iter_child_nodes(node)
                               if isinstance(c, _ast.stmt)])

    walk_module_scope(_ast.parse(src).body)
    assert bound, "模板解析不出任何綁定 ⇒ 這條防呆自己壞了"
    missing = {n for n in bound if not n.startswith("__")} - ss.ENTRY_POINT_BLACKLIST
    assert missing == set(), missing
    assert ss.RUNNER_TEMPLATE_NAMES <= ss.ENTRY_POINT_BLACKLIST


def test_every_rendered_token_outside_the_prelude_is_a_literal_or_a_renderer_name():
    """**渲染稽核**：拿一份充滿惡意但合法的字面值的 spec，逐個 token 檢查。

    主張：渲染出來的碼在前置之後，(a) 剛好 N 行 assert，(b) 裡面每一個 `Name`
    都是渲染器自己的名字（`__aeq`／`__entry`／`__vacant_ns`），(c) 其餘每一個節點
    都是常數或常數容器。也就是說：供應者交出來的東西**一個都沒有**落在會被求值成
    名字的位置上。這是「不可表達」這句話的可執行版本——1cfec80 的教訓正是
    validator 擋光了 Call/Name/Attribute，卻讓 entry_point 這個**識別字**走進去。
    """
    import ast as _ast

    nasty = [
        {"args": "['__import__(\"os\").system(\"id\")']", "expected": "None"},
        {"args": "['assert False', b'\\x00\\xff', 1e308]", "expected": "'exec'"},
        {"args": "[{'os': 'subprocess'}, (1, 2)]", "expected": "{'open': 'getattr'}"},
        {"args": "[\"'); import os; os.system('id'); ('\"]", "expected": "[1, {2: 3}]"},
        {"args": "['\\n__vacant_ns[\"f\"] = open\\n']", "expected": "True"},
    ]
    s = spec(tests=nasty)
    code = s.render()
    prelude = ss.mbpp_prelude(False, False)
    assert code.startswith(prelude)
    body = _ast.parse(code[len(prelude):]).body
    assert len(body) == 1 + len(nasty)           # 一行綁定 ＋ N 行 assert
    binding, asserts = body[0], body[1:]
    assert isinstance(binding, _ast.Assign)
    assert isinstance(binding.value, _ast.Subscript)
    assert isinstance(binding.value.value, _ast.Name)
    assert binding.value.value.id == "__vacant_ns"
    assert isinstance(binding.value.slice, _ast.Constant)
    assert binding.value.slice.value == "f"      # 名字＝一個 repr 過的字串鍵
    for node in asserts:
        assert isinstance(node, _ast.Assert)
        call = node.test
        assert isinstance(call, _ast.Call) and call.func.id == "__aeq"
        got, want, tol = call.args
        assert isinstance(got, _ast.Call) and got.func.id == "__entry"
        assert len(got.args) == 1 and isinstance(got.args[0], _ast.Starred)
        _ast.literal_eval(got.args[0].value)     # 引數：純字面值
        _ast.literal_eval(want)                  # 期望值：純字面值
        _ast.literal_eval(tol)                   # atol：純字面值
    names = {n.id for n in _ast.walk(_ast.parse(code[len(prelude):]))
             if isinstance(n, _ast.Name)}
    assert names == {"__vacant_ns", "__entry", "__aeq"}


def test_the_r452b_smuggle_payloads_never_execute_in_the_real_sandbox(tmp_path):
    """攻擊者的三份 payload 當成**字串引數**渲染出去，在真沙箱裡一個都沒跑起來。

    三份分別是 R451 三種攻擊的語意（targeted 雜湊黑名單／stateful 跨呼叫狀態／
    mimic 換掉受測函式），R452b 的走私管道是把它們塞進 `args` 再用
    `entry_point="exec"` 觸發。這裡用**合法的** entry point 渲染同樣的字面值：
    碼跑得起來、assert 照常判、而三個標記檔一個都不存在。
    """
    from ops.gain.gain_run import meets_demand

    targeted = tmp_path / "targeted.flag"
    stateful = tmp_path / "stateful.flag"
    mimic = tmp_path / "mimic.flag"
    payloads = [
        # targeted：讀候選原始碼、算 sha256、命中黑名單就丟 AssertionError
        "import hashlib\n"
        "_p = [a for a in _worker.args if isinstance(a, str)"
        " and a.endswith('candidate.py')][0]\n"
        "open(%r, 'w').write(hashlib.sha256(open(_p, 'rb').read()).hexdigest())\n"
        % str(targeted),
        # stateful：在 /tmp 留一個標記，第二次執行就換一套判準
        "import os\n"
        "open(%r, 'a').write('x')\n" % str(stateful),
        # mimic：把受測函式換掉
        "__vacant_ns['f'] = lambda *a, **k: 2\n"
        "open(%r, 'w').write('mimic')\n" % str(mimic),
    ]
    s = spec(tests=[{"args": repr([p]), "expected": "None"} for p in payloads])
    code = s.render()
    assert "exec(" not in code and "__entry(" in code
    # 候選只是把引數吃下去回 None ⇒ 這份套件會**通過**……而 payload 沒有被執行。
    ok, _ = meets_demand("def f(x):\n    return None\n", code, 10, entry_point="f")
    assert ok is True
    assert not targeted.exists() and not stateful.exists() and not mimic.exists()
