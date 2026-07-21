"""EvalPlus MBPP+ loader（G1／17 §P1-1）：釘版驗雜湊、V/GT 分離、fail-closed。

全部用合成 fixture（自己算 sha256），不碰真官方包；官方包存在時的整合門
（test_official_pack_gate）才實讀 .vacant-private——缺席即 skip，不假裝驗過。
"""

from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

import pytest

from vacant.checks import run_python_check
from vacant.codebench import (
    EVALPLUS_DEFAULT_PATH,
    EVALPLUS_MBPP_PLUS_COUNT,
    EVALPLUS_MBPP_PLUS_SHA256,
    EvalPlusMBPPLoader,
)

# --- 合成 fixture -------------------------------------------------------------
_REC1 = {
    "task_id": "Mbpp/1",
    "prompt": "Write a function to add two numbers.\n>>> add(1, 2)\n3",
    "entry_point": "add",
    "canonical_solution": "def add(a, b):\n    return a + b",
    "base_input": [[1, 2], [0, 0]],
    "plus_input": [[-1, 1], [1000000000, 1]],
    "atol": None, "contract": "", "assertion": "",
}
_REC2 = {
    "task_id": "Mbpp/2",
    "prompt": "Write a function to find the max of a list, first occurrence index.",
    "entry_point": "first_max",
    "canonical_solution": (
        "def first_max(nums):\n"
        "    best = 0\n"
        "    for i in range(1, len(nums)):\n"
        "        if nums[i] > nums[best]:\n"
        "            best = i\n"
        "    return best"
    ),
    "base_input": [[[1, 3, 2]]],
    "plus_input": [[[7]], [[5, 5, 5]]],
    "atol": None, "contract": "", "assertion": "",
}
_REC3 = {
    "task_id": "Mbpp/3",
    "prompt": "Write a function to check empty input handling.",
    "entry_point": "count_words",
    "canonical_solution": (
        "def count_words(s):\n"
        "    if isinstance(s, dict):\n"
        "        return len(s)\n"
        "    return len(s.split())"
    ),
    "base_input": [["a b"]],
    "plus_input": {"kwargs_style": True},   # 官方包實測存在的 dict 形 plus_input
    "atol": None, "contract": "", "assertion": "",
}


def _write_pack(path: Path, records: list[dict], *, gz: bool = False) -> str:
    """寫 fixture 包並回傳其 sha256。gz 用 mtime=0 保證可重現。"""
    body = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records).encode()
    if gz:
        with gzip.GzipFile(filename=str(path), mode="wb", mtime=0) as f:
            f.write(body)
    else:
        path.write_bytes(body)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _loader(tmp_path: Path, records: list[dict] | None = None, **kw) -> EvalPlusMBPPLoader:
    records = records if records is not None else [_REC1, _REC2, _REC3]
    p = tmp_path / "fixture.jsonl"
    sha = _write_pack(p, records)
    kw.setdefault("expected_sha256", sha)
    kw.setdefault("expected_count", len(records))
    return EvalPlusMBPPLoader(str(p), **kw)


# --- 正向 ---------------------------------------------------------------------
def test_loads_and_yields_tasks(tmp_path):
    loader = _loader(tmp_path)
    tasks = list(loader.iter_tasks("s0"))
    assert len(tasks) == 3
    for t in tasks:
        for k in ("task_id", "family", "prompt", "entry_point", "visible_check", "hidden_check"):
            assert k in t
        assert t["task_id"].startswith("mbppplus_")
    # family 規則標籤：REC2 prompt 含 first/index → off_by_one；REC3 含 empty → empty_input
    fams = {t["entry_point"]: t["family"] for t in tasks}
    assert fams["first_max"] == "off_by_one"
    assert fams["count_words"] == "empty_input"
    assert fams["add"] == "general"


def test_deterministic_order_per_seed(tmp_path):
    loader = _loader(tmp_path)
    a = [t["task_id"] for t in loader.iter_tasks("s0")]
    b = [t["task_id"] for t in loader.iter_tasks("s0")]
    assert a == b  # 同 seed 同序（可重放／斷點續跑的前提）


def test_check_code_actually_verifies(tmp_path):
    """產生的 hidden_check 真能判分：canonical 當候選→過；埋 bug→不過。"""
    loader = _loader(tmp_path)
    tasks = {t["entry_point"]: t for t in loader.iter_tasks("s0")}
    t = tasks["add"]
    good = "def add(a, b):\n    return a + b"
    bad = "def add(a, b):\n    return a + b + 1"
    assert run_python_check(good, t["hidden_check"]["code"]) is True
    assert run_python_check(bad, t["hidden_check"]["code"]) is False
    # visible 只含 base inputs；hidden 含 base+plus（plus 有負數案例才抓得到 bad2）
    assert run_python_check(good, t["visible_check"]["code"]) is True


def test_dict_plus_input_normalized(tmp_path):
    """dict 形 plus_input（官方包實測差異）不炸、被正規化成單一位置參數。"""
    loader = _loader(tmp_path)
    tasks = {t["entry_point"]: t for t in loader.iter_tasks("s0")}
    t = tasks["count_words"]
    assert run_python_check(
        "def count_words(s):\n"
        "    if isinstance(s, dict):\n"
        "        return len(s)\n"
        "    return len(s.split())",
        t["hidden_check"]["code"]) is True


def test_public_view_has_no_gt(tmp_path):
    """public_view 只含四個公開鍵；GT 字串不出現在任何投影欄位。"""
    loader = _loader(tmp_path)
    t = next(iter(loader.iter_tasks("s0")))
    pv = EvalPlusMBPPLoader.public_view(t)
    assert set(pv) == {"task_id", "family", "prompt", "entry_point"}
    assert "canonical_solution" not in json.dumps(pv)
    assert "plus_input" not in json.dumps(pv)


def test_gzip_pack_supported(tmp_path):
    p = tmp_path / "fixture.jsonl.gz"
    sha = _write_pack(p, [_REC1, _REC2, _REC3], gz=True)
    loader = EvalPlusMBPPLoader(str(p), expected_sha256=sha, expected_count=3)
    assert len(list(loader.iter_tasks("s0"))) == 3


# --- fail-closed 負向 -----------------------------------------------------------
def test_sha_mismatch_rejected(tmp_path):
    p = tmp_path / "f.jsonl"
    _write_pack(p, [_REC1])
    with pytest.raises(ValueError, match="sha256"):
        EvalPlusMBPPLoader(str(p), expected_sha256="0" * 64, expected_count=1)


def test_none_sha_rejected_on_nondefault_path(tmp_path):
    p = tmp_path / "f.jsonl"
    _write_pack(p, [_REC1])
    with pytest.raises(ValueError, match="None"):
        EvalPlusMBPPLoader(str(p), expected_sha256=None, expected_count=1)


def test_missing_file_rejected(tmp_path):
    with pytest.raises(FileNotFoundError):
        EvalPlusMBPPLoader(str(tmp_path / "nope.jsonl"),
                           expected_sha256="0" * 64, expected_count=1)


def test_duplicate_ids_rejected(tmp_path):
    with pytest.raises(ValueError, match="重複"):
        _loader(tmp_path, [_REC1, dict(_REC1)])


def test_missing_field_rejected(tmp_path):
    bad = {k: v for k, v in _REC1.items() if k != "canonical_solution"}
    with pytest.raises(ValueError, match="缺欄位"):
        _loader(tmp_path, [bad])


def test_wrong_type_rejected(tmp_path):
    bad = dict(_REC1, base_input="not a list")
    with pytest.raises(ValueError, match="型別"):
        _loader(tmp_path, [bad])


def test_wrong_count_rejected(tmp_path):
    p = tmp_path / "f.jsonl"
    sha = _write_pack(p, [_REC1, _REC2])
    with pytest.raises(ValueError, match="題數"):
        EvalPlusMBPPLoader(str(p), expected_sha256=sha, expected_count=3)


def test_bad_json_rejected(tmp_path):
    p = tmp_path / "f.jsonl"
    p.write_bytes(b'{"task_id": "x",\n')
    sha = hashlib.sha256(p.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="JSON"):
        EvalPlusMBPPLoader(str(p), expected_sha256=sha, expected_count=1)


# --- 官方包整合門（在場才驗；缺席＝skip，不假裝）---------------------------------
def test_official_pack_gate():
    """worker final gate：實讀 .vacant-private 官方包，驗釘版 SHA＋378 唯一題。"""
    p = Path(EVALPLUS_DEFAULT_PATH)
    if not p.exists():
        pytest.skip("官方 EvalPlus 包不在場（.vacant-private）——本機略過整合門")
    assert hashlib.sha256(p.read_bytes()).hexdigest() == EVALPLUS_MBPP_PLUS_SHA256
    loader = EvalPlusMBPPLoader()
    tasks = list(loader.iter_tasks("freeze-v1"))
    assert len(tasks) == EVALPLUS_MBPP_PLUS_COUNT
    assert len({t["task_id"] for t in tasks}) == EVALPLUS_MBPP_PLUS_COUNT
