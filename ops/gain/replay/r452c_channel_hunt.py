#!/usr/bin/env python3
# ⚠ 攻擊者（Fable 稽核）在 head b3c8514 上的原始探針，**逐字保留**——探針 C（11/11 道門
#   噴裸 ValueError）與探針 I（entry_point=None 綁定失效）已由 round452c 修補，重跑會全綠。
"""round452c（Fable 稽核）：R452b 修補之後，**還剩哪些供應者位元組到得了執行**。

這支在架構裡承重什麼
====================
R452b 把 entry_point 綁上題目、把渲染改成 `__vacant_ns['名字']` 查找。作者宣稱
「供應者剩下的自由度只有：測哪幾個輸入、mbpp 的三個比對旗標」。本支不接受宣稱，
逐條去找**反例**：任何一條讓供應者選的位元組落到可執行位置、或讓執行器整個倒下
（相關性失效）的路徑。

八組探針（每一組都落盤，通過與失敗一樣記）：
  A. entry_point 通道（走私、題目自宣告危險名、Unicode 同形、None 綁定）
  B. 字面值 payload 矩陣 → 渲染結果 AST 稽核（自由名字集合）
  C. **非 SuiteSpecError 逃逸**：validator 丟出來的例外不是 SuiteSpecError 時，
     peerexec 九道門全部只 catch SuiteSpecError ⇒ 例外穿過整條路徑
  D. 正規化雜湊碰撞（同 suite_sha256、不同渲染語意）
  E. render／validate 的 DoS（丟例外或卡住）
  F. 候選端命名遊戲（候選定義 `__aeq`／`__entry`／`__vacant_ns`／`exec`…）
     ——走**真沙箱**
  G. 題庫 entry_point 對 ENTRY_POINT_BLACKLIST 的實際命中（功能退化盤點）
  H. dialect／cmp 旋鈕

紀律：零 API、零 8765／1234、零 ssh、零 `runs/` 寫入。輸出 JSON 進本目錄。
"""
from __future__ import annotations

import ast
import json
import pathlib
import sys
import time
import traceback

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

from vacant import checks as ck            # noqa: E402
from vacant import peerexec as px          # noqa: E402
from vacant import suitespec as ss         # noqa: E402

OUT = HERE / "r452c_channel_hunt.json"

PRELUDE_NAMES = {"__aeq", "__vacant_re", "__vacant_regex_predicate",
                 "__vacant_set_equivalent", "a", "b", "atol", "allowed", "x", "y",
                 "abs", "all", "bool", "isinstance", "len", "list", "set", "tuple",
                 "type", "zip", "float", "int", "TypeError", "ValueError"}
RENDERER_NAMES = {"__vacant_ns", "__entry", "__aeq", "__tests", "__t", "__got"}


def spec_json(entry_point="f", tests=None, dialect="mbpp", **cmp_kw):
    return {"v": 1, "dialect": dialect, "entry_point": entry_point,
            "tests": tests or [{"args": "[1]", "expected": "2"}],
            "cmp": {"atol": None, "set_equivalent": False, "regex_predicate": False,
                    **cmp_kw}}


def classify(exc: BaseException) -> str:
    return ("SuiteSpecError" if isinstance(exc, ss.SuiteSpecError)
            else "ESCAPED:" + type(exc).__name__)


# ── A. entry_point 通道 ─────────────────────────────────────────────────────
def probe_a() -> dict:
    rows = []
    payload = "import os; open('/tmp/r452c_A.marker','w').write('x')"
    for task_ep, spec_ep in [("f", "f"), ("f", "exec"), ("f", "eval"), ("f", "open"),
                             ("f", "compile"), ("f", "getattr"), ("f", "print"),
                             ("f", "g"), ("f", "\uff46"), ("exec", "exec"),
                             ("sum", "sum"), ("type", "type"), ("f", None),
                             (None, "exec"), (None, "g"), (None, "f")]:
        obj = spec_json(entry_point=spec_ep if spec_ep is not None else "f",
                        tests=[{"args": "[" + repr(payload) + "]", "expected": "None"}])
        if spec_ep is None:
            obj["entry_point"] = 12345          # 非字串
        try:
            sp = ss.validate(obj, entry_point=task_ep)
            rows.append({"task_ep": task_ep, "spec_ep": spec_ep, "result": "ACCEPTED",
                         "render_head": sp.render().splitlines()[-2:]})
        except BaseException as exc:            # noqa: BLE001
            rows.append({"task_ep": task_ep, "spec_ep": spec_ep,
                         "result": classify(exc), "reason": str(exc)[:120]})
    return {"probe": "A_entry_point_channel", "rows": rows}


# ── B. 字面值 payload → 渲染 AST 稽核 ───────────────────────────────────────
PAYLOADS = [
    ("code_str", "'__import__(\"os\").system(\"id\")'"),
    ("quote_break", "\"'); import os; os.system('id'); ('\""),
    ("newline_inject", "'\\n__vacant_ns[\"f\"] = open\\n'"),
    ("ns_key_str", "'__vacant_ns'"),
    ("bytes_nul", "b'\\x00\\xff'"),
    ("surrogate", "'\\ud800'"),
    ("nonascii", "'\\u4e2d\\u6587'"),
    ("nfd_vs_nfc", "'e\\u0301'"),
    ("neg_zero", "-0.0"),
    ("denormal", "5e-324"),
    ("big_float", "1.7976931348623157e308"),
    ("float_repr", "0.1"),
    ("complex_j", "1j"),
    ("complex_negzero", "complex(-0.0,-0.0)"),        # 不是字面值 ⇒ 應該被拒
    ("complex_lit", "(-0-0j)"),
    ("inf_literal", "1e999"),
    ("nan_literal", "float('nan')"),                   # 不是字面值
    ("big_int_dec", "9" * 4290),
    ("huge_int_hex", "0x" + "f" * 4000),
    ("huge_int_bin", "0b" + "1" * 20000),
    ("huge_int_oct", "0o" + "7" * 6000),
    ("deep_nest", "[" * 39 + "1" + "]" * 39),
    ("too_deep", "[" * 60 + "1" + "]" * 60),
    ("dict_collide", "{1: 'a', True: 'b', 1.0: 'c'}"),
    ("set_mixed", "{1, 1.0, True, 'a', b'a'}"),
    ("empty_set", "set()"),
    ("frozenset", "frozenset([1])"),
    ("lambda", "lambda: 1"),
    ("fstring", "f'{1}'"),
    ("name", "os"),
    ("call", "open('/etc/passwd')"),
    ("attr", "().__class__"),
    ("ellipsis", "..."),
    ("walrus", "(x := 1)"),
]


def strip_prelude(code: str, spec: "ss.SuiteSpec") -> str:
    """砍掉**渲染器自己寫死**的前置，只留下供應者影響得到的那幾行。

    稽核必須看這一段：前置本身有 `import re as __vacant_re`、`.Match`、
    `isinstance`／`zip`／`abs`…，那些是渲染器的常數字串，混進來會把訊號洗掉。
    """
    head = (ss.mbpp_prelude(spec.regex_predicate, spec.set_equivalent)
            if spec.dialect == "mbpp" else ss.lcb_prelude())
    assert code.startswith(head.rstrip("\n")), "前置不是渲染器那一份"
    return code[len(head.rstrip("\n")):]


def audit_render(code: str) -> dict:
    """渲染結果的 AST 稽核：自由名字、Call 目標、有沒有 Import／Attribute。"""
    tree = ast.parse(code)
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    calls = {n.func.id for n in ast.walk(tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    attrs = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    imports = [type(n).__name__ for n in ast.walk(tree)
               if isinstance(n, (ast.Import, ast.ImportFrom))]
    extra = names - PRELUDE_NAMES - RENDERER_NAMES
    return {"free_names_outside_prelude": sorted(extra), "calls": sorted(calls),
            "attrs": sorted(attrs), "imports": imports}


def probe_b() -> dict:
    rows = []
    for name, lit in PAYLOADS:
        for slot in ("args", "expected"):
            tests = ([{"args": f"[{lit}]", "expected": "None"}] if slot == "args"
                     else [{"args": "[1]", "expected": lit}])
            try:
                sp = ss.validate(spec_json(tests=tests), entry_point="f")
            except BaseException as exc:            # noqa: BLE001
                rows.append({"payload": name, "slot": slot, "result": classify(exc),
                             "reason": str(exc)[:120]})
                continue
            try:
                code = sp.render()
                aud = audit_render(strip_prelude(code, sp))
                rows.append({"payload": name, "slot": slot, "result": "ACCEPTED",
                             "canonical": (sp.tests[0].args if slot == "args"
                                           else sp.tests[0].expected)[:80],
                             **aud})
            except BaseException as exc:            # noqa: BLE001
                rows.append({"payload": name, "slot": slot,
                             "result": "RENDER_" + classify(exc),
                             "reason": str(exc)[:120]})
    bad = [r for r in rows
           if r.get("result") == "ACCEPTED"
           and (r["free_names_outside_prelude"] or r["imports"]
                or set(r["calls"]) - {"__aeq", "__entry"} or r["attrs"])]
    return {"probe": "B_literal_payloads", "n": len(rows), "violations": bad,
            "rows": rows}


# ── C. 非 SuiteSpecError 逃逸（九道門）──────────────────────────────────────
NONCE = "r452c-nonce-0123456789"
POISON = spec_json(tests=[{"args": "[1]", "expected": "0x" + "f" * 4000}])


def probe_c() -> dict:
    """一份「合法字面值」的 spec，讓 validator 丟出**不是** SuiteSpecError 的例外。

    `ast.literal_eval` 收 16 進位字面值（不受 int_max_str_digits 限制），
    `emit_literal` 再 `repr()` 它就撞上 4300 位十進位轉換上限 ⇒ 裸 `ValueError`。
    peerexec 每一道門都只 `except SuiteSpecError`，於是例外穿過整條路徑。
    """
    rows = []
    task = {"task_id": "t", "entry_point": "f",
            "visible_check": {"code": ""}, "hidden_check": {"code": ""}}

    def rec(gate, fn):
        try:
            fn()
            rows.append({"gate": gate, "result": "no_exception"})
        except BaseException as exc:                # noqa: BLE001
            rows.append({"gate": gate, "result": classify(exc), "reason": str(exc)[:110]})

    rec("suitespec.validate", lambda: ss.validate(POISON, entry_point="f"))
    rec("peerexec.as_suite_spec", lambda: px.as_suite_spec(POISON, "f"))

    ident, book = px.Identity.generate(), px.Logbook()
    rec("commit_suite", lambda: px.commit_suite(
        book, ident, task_id="t", suite=POISON, nonce=NONCE, entry_point="f",
        gauge=px.GaugeRecord("x", "y", 4, True, True), ts_ms=1))
    ex = px.Executor("x", px.Identity.generate(), px.Logbook(),
                     lambda code, t: px.ProbeResult(True))
    rec("Executor.attest", lambda: ex.attest(task, "def f(a): return a",
                                             suite=POISON, ts_ms=1))
    rec("select_by_quorum", lambda: px.select_by_quorum(
        task, [("def f(a): return a", "w0")], [ex], suite=POISON,
        quorum=1, ts_ms=1))
    rec("run_suite_gauge", lambda: px.run_suite_gauge(
        POISON, "def f(a): return a", ["def f(a): return None"], entry_point="f"))
    # suite_gate 需要一筆真的 commit，用乾淨的 spec 承諾、再用毒 spec 揭露
    clean = spec_json()
    b2, id2 = px.Logbook(), px.Identity.generate()
    entry = px.commit_suite(b2, id2, task_id="t", suite=clean, nonce=NONCE,
                            entry_point="f",
                            gauge=px.GaugeRecord(
                                ss.validate(clean, entry_point="f").suite_sha256,
                                "r", 4, True, True), ts_ms=1)
    rec("suite_gate", lambda: px.suite_gate(entry, POISON, NONCE, entry_point="f"))
    rec("open_suite", lambda: px.open_suite(entry, POISON, NONCE, entry_point="f"))
    rec("gauged_suite_index",
        lambda: px.gauged_suite_index([(entry, POISON, NONCE, "f")]))
    v0 = px.Verdict("t", "d", "s", None, 0, 0, (), (), (), (), (), (), (), 1, 0,
                    "unchecked")
    rec("challenge_rerun", lambda: px.challenge_rerun(
        task, "def f(a): return a", [ex], v0, suite=POISON, quorum=1, ts_ms=1))
    rec("commit_suite_with_gauge", lambda: px.commit_suite_with_gauge(
        px.Logbook(), px.Identity.generate(), task_id="t", suite=POISON, nonce=NONCE,
        reference="def f(a): return a", entry_point="f",
        broken_stubs=["def f(a): return None"], ts_ms=1))
    return {"probe": "C_non_suitespecerror_escape", "rows": rows,
            "escaped_gates": [r["gate"] for r in rows
                              if str(r["result"]).startswith("ESCAPED")]}


# ── D. 正規化雜湊碰撞 ───────────────────────────────────────────────────────
def probe_d() -> dict:
    """找「同 suite_sha256、不同渲染」的兩份 spec。

    渲染是 `to_json()` 的純函式，而 `suite_sha256` ＝ hash(canonical_bytes(to_json()))，
    所以碰撞等價於 canonical_bytes 在 to_json 的值域上非單射。逐條試會讓
    JSON 混同的候選（int/float、bool/int、NFC/NFD、代理對、-0.0）。
    """
    cands = [
        ("int_vs_float_expected", spec_json(tests=[{"args": "[1]", "expected": "1"}]),
         spec_json(tests=[{"args": "[1]", "expected": "1.0"}])),
        ("bool_vs_int_expected", spec_json(tests=[{"args": "[1]", "expected": "True"}]),
         spec_json(tests=[{"args": "[1]", "expected": "1"}])),
        ("negzero_vs_zero", spec_json(tests=[{"args": "[1]", "expected": "-0.0"}]),
         spec_json(tests=[{"args": "[1]", "expected": "0.0"}])),
        ("atol_int_vs_float", spec_json(atol=1), spec_json(atol=1.0)),
        ("atol_zero_negzero", spec_json(atol=0.0), spec_json(atol=-0.0)),
        ("nfc_vs_nfd", spec_json(tests=[{"args": "['\\u00e9']", "expected": "None"}]),
         spec_json(tests=[{"args": "['e\\u0301']", "expected": "None"}])),
        ("tuple_vs_list_args", spec_json(tests=[{"args": "(1,)", "expected": "None"}]),
         spec_json(tests=[{"args": "[1]", "expected": "None"}])),
        ("set_order", spec_json(tests=[{"args": "[{1,2,3}]", "expected": "None"}]),
         spec_json(tests=[{"args": "[{3,2,1}]", "expected": "None"}])),
        ("dict_dup_key", spec_json(tests=[{"args": "[{1:'a',True:'b'}]",
                                           "expected": "None"}]),
         spec_json(tests=[{"args": "[{1:'b'}]", "expected": "None"}])),
        ("str_escape_style", spec_json(tests=[{"args": "['a\\x41']", "expected": "None"}]),
         spec_json(tests=[{"args": "['aA']", "expected": "None"}])),
    ]
    rows = []
    for name, a, b in cands:
        try:
            sa, sb = ss.validate(a, entry_point="f"), ss.validate(b, entry_point="f")
        except BaseException as exc:                # noqa: BLE001
            rows.append({"pair": name, "result": classify(exc), "reason": str(exc)[:100]})
            continue
        rows.append({"pair": name, "same_sha": sa.suite_sha256 == sb.suite_sha256,
                     "same_render": sa.render() == sb.render(),
                     "collision": (sa.suite_sha256 == sb.suite_sha256
                                   and sa.render() != sb.render())})
    # 隨機 fuzz：同 sha 必須同 render
    import random
    rng = random.Random(20260906)
    seen: dict[str, str] = {}
    coll = []
    atoms = ["1", "1.0", "True", "False", "None", "'a'", "b'a'", "-0.0", "1j",
             "[1]", "(1,)", "{1}", "{'a':1}", "0", "-1", "''", "'\\u00e9'"]
    for _ in range(4000):
        t = [{"args": "[" + rng.choice(atoms) + "]", "expected": rng.choice(atoms)}
             for _ in range(rng.randint(1, 3))]
        obj = spec_json(tests=t, atol=rng.choice([None, 0.0, 1e-9, 1.0]),
                        set_equivalent=rng.choice([True, False]),
                        regex_predicate=rng.choice([True, False]))
        try:
            sp = ss.validate(obj, entry_point="f")
        except ss.SuiteSpecError:
            continue
        h, r = sp.suite_sha256, sp.render()
        if h in seen and seen[h] != r:
            coll.append(h)
        seen[h] = r
    return {"probe": "D_canonicalisation_collision", "rows": rows,
            "fuzz_n_specs": len(seen), "fuzz_collisions": coll,
            "targeted_collisions": [r["pair"] for r in rows if r.get("collision")]}


# ── E. render／validate DoS ────────────────────────────────────────────────
def probe_e() -> dict:
    rows = []

    def timed(name, fn):
        t0 = time.time()
        try:
            fn()
            rows.append({"case": name, "result": "ok",
                         "elapsed_s": round(time.time() - t0, 3)})
        except BaseException as exc:                # noqa: BLE001
            rows.append({"case": name, "result": classify(exc),
                         "reason": str(exc)[:100],
                         "elapsed_s": round(time.time() - t0, 3)})

    # 1) 上限尺寸的合法 spec：2000 條測資
    big = spec_json(tests=[{"args": "[%d]" % i, "expected": str(i)}
                           for i in range(2000)])
    timed("2000_tests_validate", lambda: ss.validate(big, entry_point="f"))
    sp = ss.validate(big, entry_point="f")
    timed("2000_tests_render", sp.render)
    # 2) 單條 200k 字元的字串字面值
    wide = spec_json(tests=[{"args": "['" + "a" * 199_000 + "']", "expected": "None"}])
    timed("200k_char_literal", lambda: ss.validate(wide, entry_point="f"))
    # 3) MAX_SPEC_BYTES 之上：檢查是在**做完所有工**之後才拒
    huge = spec_json(tests=[{"args": "['" + "a" * 190_000 + "']", "expected": "None"}
                            for _ in range(40)])
    timed("8MB_spec_rejected_last", lambda: ss.validate(huge, entry_point="f"))
    # 4) 深巢狀 + 寬度
    nest = "[" + ",".join("[[1]]" for _ in range(20_000)) + "]"
    timed("wide_nested", lambda: ss.validate(
        spec_json(tests=[{"args": "[" + nest + "]", "expected": "None"}]),
        entry_point="f"))
    # 5) 已驗過的 spec，render 會不會丟例外
    timed("render_never_raises", lambda: [ss.validate(
        spec_json(tests=[{"args": "[1]", "expected": e}]),
        entry_point="f").render() for e in ("1", "'a'", "-0.0", "1j", "b'\\x00'")])
    return {"probe": "E_render_validate_dos", "rows": rows}


# ── F. 候選端命名遊戲（真沙箱）──────────────────────────────────────────────
CAND_VARIANTS = {
    "honest": "def f(a):\n    return a + 1\n",
    "wrong": "def f(a):\n    return 0\n",
    "wrong_plus_fake_aeq": (
        "def f(a):\n    return 0\n"
        "def __aeq(a, b, atol):\n    return True\n"),
    "wrong_plus_fake_entry": (
        "def f(a):\n    return 0\n"
        "def __entry(*a, **k):\n    return 2\n"),
    "wrong_plus_flag_fn": (
        "def f(a):\n    return 0\n"
        "def __vacant_set_equivalent(*a, **k):\n    return True\n"
        "def __vacant_regex_predicate(*a, **k):\n    return True\n"),
    "wrong_plus_ns_assign": (
        "def f(a):\n    return 0\n"
        "__vacant_ns = {'f': (lambda a: 2)}\n"),
    "wrong_plus_helper": "def f(a):\n    return 0\ndef helper(a):\n    return a + 1\n",
    "no_entry_point": "def g(a):\n    return a + 1\n",
}


def probe_f() -> dict:
    spec = ss.validate(spec_json(tests=[{"args": "[1]", "expected": "2"}]),
                       entry_point="f")
    code = spec.render()
    rows = []
    for name, src in CAND_VARIANTS.items():
        try:
            ok = ck.run_python_check(src, code, timeout=10,
                                     allowed_entry_points=("f",))
            rows.append({"candidate": name, "verdict": ok})
        except BaseException as exc:                # noqa: BLE001
            rows.append({"candidate": name, "verdict": "error:" + type(exc).__name__})
    # 只有 honest 應該是 True
    bad = [r for r in rows if (r["candidate"] != "honest") and r["verdict"] is True]
    return {"probe": "F_candidate_name_games", "rows": rows, "false_passes": bad,
            "rendered": code}


# ── G. 題庫 entry_point 對黑名單的命中 ──────────────────────────────────────
def probe_g() -> dict:
    import peer_exec_sim as sim                     # noqa: PLC0415
    out = {}
    for run in ("g_r446_eq5_mbpp", "g_r443_gemma_lcb"):
        try:
            tasks, cands = sim.load_pool(run)
        except BaseException as exc:                # noqa: BLE001
            out[run] = {"error": f"{type(exc).__name__}:{exc}"[:160]}
            continue
        hits, weird = [], []
        for tid, t in sorted(tasks.items()):
            ep = t.get("entry_point")
            if not isinstance(ep, str) or not ep:
                weird.append({"task_id": tid, "entry_point": ep})
                continue
            if ep in ss.ENTRY_POINT_BLACKLIST or ep.startswith("__") \
                    or not ep.isidentifier():
                hits.append({"task_id": tid, "entry_point": ep})
        out[run] = {"n_tasks": len(tasks), "n_in_pool": len(cands),
                    "blacklist_hits": hits, "missing_entry_point": weird}
    return {"probe": "G_corpus_entry_points", "runs": out,
            "task_ownable_builtins": sorted(ss.TASK_OWNABLE_BUILTINS)}


# ── H. dialect／cmp 旋鈕 ────────────────────────────────────────────────────
def probe_h() -> dict:
    cases = [
        ("lcb_with_atol", {"dialect": "lcb", "cmp": {"atol": 1e9}}),
        ("lcb_with_seteq", {"dialect": "lcb", "cmp": {"set_equivalent": True}}),
        ("lcb_clean", {"dialect": "lcb", "cmp": {}}),
        ("unknown_dialect", {"dialect": "mbpp2", "cmp": {}}),
        ("atol_bool", {"cmp": {"atol": True}}),
        ("atol_neg", {"cmp": {"atol": -1.0}}),
        ("atol_inf", {"cmp": {"atol": 1e999}}),
        ("atol_huge", {"cmp": {"atol": 1e308}}),
        ("atol_str", {"cmp": {"atol": "1"}}),
        ("cmp_extra_key", {"cmp": {"atol": None, "wat": 1}}),
        ("cmp_not_mapping", {"cmp": [1]}),
        ("seteq_int", {"cmp": {"set_equivalent": 1}}),
        ("bad_version", {"v": 2}),
        ("tests_str", {"tests": "abc"}),
        ("tests_empty", {"tests": []}),
        ("test_extra_key", {"tests": [{"args": "[1]", "expected": "1", "x": 1}]}),
        ("args_not_positional", {"tests": [{"args": "1", "expected": "1"}]}),
        ("args_dict", {"tests": [{"args": "{'a':1}", "expected": "1"}]}),
        ("raw_code_str", "def check(): pass"),
    ]
    rows = []
    for name, patch in cases:
        obj = patch if isinstance(patch, str) else {**spec_json(), **patch}
        if isinstance(patch, dict) and "cmp" in patch and isinstance(patch["cmp"], dict):
            obj["cmp"] = patch["cmp"]
        try:
            sp = ss.validate(obj, entry_point="f")
            rows.append({"case": name, "result": "ACCEPTED",
                         "render_tail": sp.render().splitlines()[-1][:100]})
        except BaseException as exc:                # noqa: BLE001
            rows.append({"case": name, "result": classify(exc), "reason": str(exc)[:110]})
    return {"probe": "H_dialect_cmp", "rows": rows}


# ── I. entry_point=None 的綁定失效（端到端）────────────────────────────────
def probe_i() -> dict:
    """題目 dict **沒有** `entry_point` 欄位時，R452b 的綁定整條變成 no-op。

    `validate` 寫的是 `if entry_point is not None and ep != entry_point`，所以
    `None` 是「跳過檢查」不是「一定不符」。`Executor.attest`／`select_by_quorum`
    ／`challenge_rerun` 都用 `task.get("entry_point")`，欄位不在就傳 None 進去。
    `peerexec.as_suite_spec` 的 docstring 說「可以是 None，但那樣一定不相符 ⇒ 拒」
    ——本探針就是去核那句話。
    """
    task = {"task_id": "t"}                      # 刻意沒有 entry_point
    obj = {"v": 1, "dialect": "mbpp", "entry_point": "helper",
           "tests": [{"args": "[1]", "expected": "2"}], "cmp": {}}
    row: dict = {"task_dict_has_entry_point": "entry_point" in task,
                 "spec_entry_point": "helper"}
    try:
        sp = px.as_suite_spec(obj, task.get("entry_point"))
        row["as_suite_spec"] = "ACCEPTED"
        row["render_binding"] = sp.render().splitlines()[-2]
        ident, book = px.Identity.generate(), px.Logbook()
        e = px.commit_suite(book, ident, task_id="t", suite=sp, nonce=NONCE,
                            entry_point=task.get("entry_point"),
                            gauge=px.GaugeRecord(sp.suite_sha256, "r", 4, True, True),
                            ts_ms=1)
        row["commit_suite"] = "ACCEPTED"
        row["committed_entry_point"] = e.payload["entry_point"]
        row["commit_version"] = e.payload["v"]
        row["suite_gate"] = px.suite_gate(e, sp, NONCE,
                                          entry_point=task.get("entry_point"))
    except BaseException as exc:                 # noqa: BLE001
        row["result"] = classify(exc)
        row["reason"] = str(exc)[:120]
    return {"probe": "I_none_binding_fail_open", "row": row,
            "docstring_claim_holds": row.get("as_suite_spec") != "ACCEPTED"}


def main() -> None:
    probes = [probe_a, probe_b, probe_c, probe_d, probe_e, probe_f, probe_g, probe_h,
              probe_i]
    out = {"head": "b3c8514", "results": []}
    for p in probes:
        t0 = time.time()
        try:
            r = p()
        except BaseException:                        # noqa: BLE001
            r = {"probe": p.__name__, "crashed": traceback.format_exc()[-1500:]}
        r["elapsed_s"] = round(time.time() - t0, 2)
        out["results"].append(r)
        print(f"{r['probe'] if 'probe' in r else p.__name__}: {r['elapsed_s']}s",
              flush=True)
    OUT.write_text(json.dumps(out, indent=1, sort_keys=True, default=str))
    print("落盤：", OUT)


if __name__ == "__main__":
    main()
