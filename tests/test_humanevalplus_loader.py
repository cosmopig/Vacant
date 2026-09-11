"""EvalPlus HumanEval+ loader（R529）：釘版驗雜湊、V/GT 分離、fail-closed。

與 `tests/test_evalplus_loader.py` 同一套紀律，另外釘住**三件 HumanEval 特有的事**
（每一件都對應一種會安靜跑錯的壞法）：

  1. `canonical_solution` 是**函式體**不是完整函式 ⇒ 參考解必須是
     `prompt + canonical_solution`。拼錯的話量具會在**每一題**上報
     「參考解不通過」，那長得像題庫壞了而不是拼法錯了。
  2. **不准**借用 MBPP 的 `_norm_inputs`：它按 `Mbpp/<整數>` 查一張型別還原表，
     而 `HumanEval/<整數>` 也是整數 ⇒ 借用＝把 MBPP 的 tuple／set／complex
     規則張冠李戴地套到同號的 HumanEval 題上。
  3. `visible_check` 只有 base 輸入、`hidden_check` ＝ base ＋ plus；
     `canonical_solution`／`plus_input`／`test` 不得出現在 prompt 或 public_view。

全部用合成 fixture（自己算 sha256），不碰真官方包；官方包存在時的整合門
（`test_official_pack_gate`）才實讀 `.vacant-private`——缺席即 skip，不假裝驗過。
"""

from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

import pytest

from vacant.checks import run_python_check
from vacant.codebench import (
    EVALPLUS_HUMANEVAL_DEFAULT_PATH,
    EVALPLUS_HUMANEVAL_PLUS_COUNT,
    EVALPLUS_HUMANEVAL_PLUS_SHA256,
    EvalPlusHumanEvalLoader,
    _he_norm_inputs,
    _norm_inputs,
)

# --- 合成 fixture（形狀照官方 v0.1.10：prompt＝簽名＋docstring，canonical＝函式體）---
_REC1 = {
    "task_id": "HumanEval/2",       # ⚠ 2 在 MBPP 的 tuple 還原表裡——第 2 條測試用它
    "prompt": (
        "from typing import List\n\n\n"
        "def add_all(xs: List[int]) -> int:\n"
        '    """ Sum a list of ints.\n'
        "    >>> add_all([1, 2])\n"
        "    3\n"
        '    """\n'
    ),
    "entry_point": "add_all",
    "canonical_solution": "\n    total = 0\n    for x in xs:\n        total += x\n    return total\n",
    "base_input": [[[1, 2]], [[0]]],
    "plus_input": [[[-1, 1]], [[5, 5, 5]]],
    "atol": 0, "contract": "", "test": "GT_ONLY_TEST_BODY",
}
_REC2 = {
    "task_id": "HumanEval/63",      # 63 在 MBPP 的 nested_tuple 還原表裡
    "prompt": (
        "def first_index(xs, target):\n"
        '    """ Return the index of the first occurrence, or -1. """\n'
    ),
    "entry_point": "first_index",
    "canonical_solution": (
        "\n    for i, x in enumerate(xs):\n"
        "        if x == target:\n"
        "            return i\n"
        "    return -1\n"
    ),
    "base_input": [[[1, 3, 2], 3]],
    "plus_input": [[[7], 7], [[5, 5, 5], 9]],
    "atol": 0, "contract": "", "test": "GT_ONLY_TEST_BODY",
}
_REC3 = {
    "task_id": "HumanEval/4",
    "prompt": (
        "def mean_abs(xs):\n"
        '    """ Mean absolute deviation. """\n'
    ),
    "entry_point": "mean_abs",
    "canonical_solution": (
        "\n    m = sum(xs) / len(xs)\n"
        "    return sum(abs(x - m) for x in xs) / len(xs)\n"
    ),
    "base_input": [[[1.0, 2.0, 3.0, 4.0]]],
    "plus_input": [[[1.0, 2.0]]],
    "atol": 1e-6, "contract": "", "test": "GT_ONLY_TEST_BODY",
}


def _write_pack(path: Path, records: list[dict], *, gz: bool = False) -> str:
    body = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records).encode()
    if gz:
        with gzip.GzipFile(filename=str(path), mode="wb", mtime=0) as f:
            f.write(body)
    else:
        path.write_bytes(body)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _loader(tmp_path: Path, records: list[dict] | None = None,
            **kw) -> EvalPlusHumanEvalLoader:
    records = records if records is not None else [_REC1, _REC2, _REC3]
    p = tmp_path / "he_fixture.jsonl"
    sha = _write_pack(p, records)
    kw.setdefault("expected_sha256", sha)
    kw.setdefault("expected_count", len(records))
    return EvalPlusHumanEvalLoader(str(p), **kw)


# --- 正向 ---------------------------------------------------------------------
def test_loads_and_yields_tasks(tmp_path):
    tasks = list(_loader(tmp_path).iter_tasks("s0"))
    assert len(tasks) == 3
    for t in tasks:
        for k in ("task_id", "family", "prompt", "entry_point",
                  "visible_check", "hidden_check"):
            assert k in t
        assert t["task_id"].startswith("humanevalplus_")


def test_task_ids_do_not_collide_with_the_other_banks(tmp_path):
    """`humanevalplus_` 前綴是跨題庫分析唯一分得出來源的東西。"""
    ids = {t["task_id"] for t in _loader(tmp_path).iter_tasks("s0")}
    assert all(not i.startswith("mbppplus_") and not i.startswith("lcb_") for i in ids)


def test_canonical_is_prompt_plus_body_and_actually_verifies(tmp_path):
    """第 1 條：`prompt + canonical_solution` 才是完整參考解，而且真能判分。"""
    tasks = {t["entry_point"]: t for t in _loader(tmp_path).iter_tasks("s0")}
    t = tasks["add_all"]
    good = "def add_all(xs):\n    return sum(xs)\n"
    bad = "def add_all(xs):\n    return sum(xs) + 1\n"
    assert run_python_check(good, t["hidden_check"]["code"]) is True
    assert run_python_check(bad, t["hidden_check"]["code"]) is False
    assert run_python_check(good, t["visible_check"]["code"]) is True
    # 參考解單獨拼出來要編譯得過（拼反了就是 IndentationError）
    src = EvalPlusHumanEvalLoader.canonical_source(_REC1)
    compile(src, "<fixture>", "exec")
    # `from typing import List` 要在白名單裡才過得了沙箱——三條臂走的是
    # `gain_run._GAIN_ALLOWED_IMPORTS`（含 typing），這裡照同一份白名單驗。
    assert run_python_check(src, t["hidden_check"]["code"],
                            allowed_imports=("typing",)) is True


def test_body_only_canonical_alone_would_not_compile():
    """把「拼法錯了」與「題庫壞了」分開：函式體單獨編譯必定失敗。"""
    with pytest.raises((SyntaxError, IndentationError)):
        compile(_REC1["canonical_solution"], "<fixture>", "exec")


def test_humaneval_inputs_are_not_run_through_the_mbpp_type_registry():
    """第 2 條：MBPP 的還原表按整數編號查——`HumanEval/2` 會誤中 `Mbpp/2`。"""
    raw = [[[1, 2]], [[0]]]
    assert _he_norm_inputs(raw) == [[[1, 2]], [[0]]]
    # 同一筆輸入餵給 MBPP 那支、帶 HumanEval 的 task_id ⇒ 被改成 tuple（錯的）
    assert _norm_inputs(raw, "HumanEval/2") == [[(1, 2)], [(0,)]]
    assert _he_norm_inputs(raw) != _norm_inputs(raw, "HumanEval/2")


def test_float_atol_is_honoured(tmp_path):
    tasks = {t["entry_point"]: t for t in _loader(tmp_path).iter_tasks("s0")}
    t = tasks["mean_abs"]
    near = ("def mean_abs(xs):\n"
            "    m = sum(xs) / len(xs)\n"
            "    return sum(abs(x - m) for x in xs) / len(xs) + 1e-9\n")
    assert run_python_check(near, t["hidden_check"]["code"]) is True


def test_deterministic_order_per_seed(tmp_path):
    loader = _loader(tmp_path)
    a = [t["task_id"] for t in loader.iter_tasks("s0")]
    b = [t["task_id"] for t in loader.iter_tasks("s0")]
    assert a == b


def test_visible_is_base_only_and_hidden_is_base_plus_plus(tmp_path):
    """第 3 條：可見＝base、隱藏＝base＋plus，而且 plus 的值不得出現在 visible。"""
    tasks = {t["entry_point"]: t for t in _loader(tmp_path).iter_tasks("s0")}
    t = tasks["first_index"]
    vis, hid = t["visible_check"]["code"], t["hidden_check"]["code"]
    assert vis.count("\nassert ") == len(_REC2["base_input"])
    assert hid.count("\nassert ") == len(_REC2["base_input"]) + len(_REC2["plus_input"])
    assert "[7]" not in vis and "[7]" in hid


def test_public_view_and_prompt_carry_no_ground_truth(tmp_path):
    t = next(iter(_loader(tmp_path).iter_tasks("s0")))
    pv = EvalPlusHumanEvalLoader.public_view(t)
    assert set(pv) == {"task_id", "family", "prompt", "entry_point"}
    blob = json.dumps(pv, ensure_ascii=False)
    assert "GT_ONLY_TEST_BODY" not in blob
    assert "plus_input" not in blob
    for rec in (_REC1, _REC2, _REC3):
        body = rec["canonical_solution"].strip()
        assert body not in t["prompt"]
        assert "GT_ONLY_TEST_BODY" not in t["prompt"]


def test_gzip_pack_supported(tmp_path):
    p = tmp_path / "he.jsonl.gz"
    sha = _write_pack(p, [_REC1, _REC2, _REC3], gz=True)
    loader = EvalPlusHumanEvalLoader(str(p), expected_sha256=sha, expected_count=3)
    assert len(list(loader.iter_tasks("s0"))) == 3


# --- fail-closed 負向 -----------------------------------------------------------
def test_sha_mismatch_rejected(tmp_path):
    p = tmp_path / "f.jsonl"
    _write_pack(p, [_REC1])
    with pytest.raises(ValueError, match="sha256"):
        EvalPlusHumanEvalLoader(str(p), expected_sha256="0" * 64, expected_count=1)


def test_none_sha_rejected_on_nondefault_path(tmp_path):
    p = tmp_path / "f.jsonl"
    _write_pack(p, [_REC1])
    with pytest.raises(ValueError, match="None"):
        EvalPlusHumanEvalLoader(str(p), expected_sha256=None, expected_count=1)


def test_missing_file_rejected(tmp_path):
    with pytest.raises(FileNotFoundError):
        EvalPlusHumanEvalLoader(str(tmp_path / "nope.jsonl"),
                                expected_sha256="0" * 64, expected_count=1)


def test_duplicate_ids_rejected(tmp_path):
    with pytest.raises(ValueError, match="重複"):
        _loader(tmp_path, [_REC1, dict(_REC1)])


def test_missing_field_rejected(tmp_path):
    bad = {k: v for k, v in _REC1.items() if k != "canonical_solution"}
    with pytest.raises(ValueError, match="缺欄位"):
        _loader(tmp_path, [bad])


def test_wrong_type_rejected(tmp_path):
    with pytest.raises(ValueError, match="型別"):
        _loader(tmp_path, [dict(_REC1, base_input="not a list")])


def test_wrong_count_rejected(tmp_path):
    p = tmp_path / "f.jsonl"
    sha = _write_pack(p, [_REC1, _REC2])
    with pytest.raises(ValueError, match="題數"):
        EvalPlusHumanEvalLoader(str(p), expected_sha256=sha, expected_count=3)


def test_bad_json_rejected(tmp_path):
    p = tmp_path / "f.jsonl"
    p.write_bytes(b'{"task_id": "x",\n')
    sha = hashlib.sha256(p.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="JSON"):
        EvalPlusHumanEvalLoader(str(p), expected_sha256=sha, expected_count=1)


def test_canonical_that_does_not_compose_is_rejected(tmp_path):
    """拼法錯了（函式體沒有縮排、或順序反了）⇒ 建構就停，不要等量具在 164 題上報紅。"""
    bad = dict(_REC1, canonical_solution="return sum(xs)\n")
    with pytest.raises(ValueError, match="編譯不過"):
        _loader(tmp_path, [bad])


def test_empty_canonical_is_rejected(tmp_path):
    """空的參考解會讓「什麼都判通過」長得像量具通過 ⇒ 建構就拒收。"""
    with pytest.raises(ValueError, match="空的"):
        _loader(tmp_path, [dict(_REC1, canonical_solution="   \n")])


def test_canonical_without_the_entry_point_is_rejected(tmp_path):
    bad = dict(_REC1, entry_point="not_defined_anywhere")
    with pytest.raises(ValueError, match="entry_point"):
        _loader(tmp_path, [bad])


# --- 官方包整合門（在場才驗；缺席＝skip，不假裝）---------------------------------
def test_official_pack_gate():
    """實讀 `.vacant-private` 官方包，驗釘版 SHA ＋ 164 題唯一 ＋ V/GT 分離。"""
    p = Path(EVALPLUS_HUMANEVAL_DEFAULT_PATH)
    if not p.exists():
        pytest.skip("官方 HumanEval+ 包不在場（.vacant-private）——本機略過整合門")
    assert hashlib.sha256(p.read_bytes()).hexdigest() == EVALPLUS_HUMANEVAL_PLUS_SHA256
    loader = EvalPlusHumanEvalLoader()
    tasks = list(loader.iter_tasks("r529-gate"))
    assert len(tasks) == EVALPLUS_HUMANEVAL_PLUS_COUNT
    assert len({t["task_id"] for t in tasks}) == EVALPLUS_HUMANEVAL_PLUS_COUNT
    for t in tasks:
        assert t["visible_check"]["code"] and t["hidden_check"]["code"]
        assert len(t["hidden_check"]["code"]) >= len(t["visible_check"]["code"])
