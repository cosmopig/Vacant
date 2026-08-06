"""檔案庫索引不准說謊（2026-08-06）。

2026-08-03 出過一次這個問題：對抗式複驗的裁決只寫在 `publish_archive.py` 裡（餵網頁
用），而 `build_archive_index.py` 產出的 `_index/claims.json` 完全沒有裁決欄位。於是
**給 agent 讀的索引宣稱那 12 條都成立，而網頁上寫著其中 6 條有問題**。

這是這個專題最不該犯的錯。索引的全部價值就在於它不會說謊，而讀索引的 agent 沒有網頁
可以對照——樂觀的索引比沒有索引更糟。

修法是把裁決抽成 `examples/verdicts.py` 當單一真相來源，兩支腳本都從那裡讀。下面這幾支
釘住那個修法：任何一條裁決掉出索引、或裁決指向不存在的宣稱，都要在這裡失敗。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def _load(name: str):
    """從 examples/ 載入腳本模組。examples 不是套件，所以走檔案路徑。"""
    spec = importlib.util.spec_from_file_location(name, EXAMPLES / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules.setdefault(name, mod)      # build_archive_index 會 import verdicts
    sys.path.insert(0, str(EXAMPLES))
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.path.remove(str(EXAMPLES))
    return mod


@pytest.fixture(scope="module")
def verdicts():
    return _load("verdicts")


@pytest.fixture(scope="module")
def index(verdicts):
    return _load("build_archive_index")


def test_every_verdict_points_at_a_real_claim(verdicts, index):
    """裁決不能是孤兒——指向不存在的宣稱 id 代表宣稱被改名或刪掉了，
    而裁決留在原地假裝還在管事。"""
    ids = {c["id"] for c in index.CLAIMS}
    orphans = sorted(set(verdicts.VERDICTS) - ids)
    assert not orphans, f"裁決指向不存在的宣稱：{orphans}"


def test_every_claim_carries_a_verdict(verdicts, index):
    """每條宣稱都要有 verdict 欄位。沒有欄位 ≠ 沒問題——它會被讀成「沒問題」。"""
    for c in index.CLAIMS:
        v = verdicts.verdict_for(c["id"])
        assert v.get("verdict"), f"{c['id']} 沒有裁決欄位"


def test_unreviewed_is_not_a_pass(verdicts):
    """未複驗必須明確標出來，而且不能長得像通過。

    網頁上這個徽章曾經是綠色的，會被讀成「通過複驗」；改成中性色的同時，
    資料端也要有一個明確的值，不能靠「欄位不存在」來表達。
    """
    assert verdicts.verdict_for("此宣稱不存在")["verdict"] == verdicts.UNREVIEWED
    assert verdicts.UNREVIEWED not in ("", "ok", "passed", "pass")


def test_refuted_verdicts_carry_the_correction(verdicts):
    """被推翻的宣稱一定要附「更正後的說法」與「複驗者實測」。

    只說「這條是錯的」而不給正確版本，等於把錯誤留在原地又不負責——
    引用的人只會回頭用原文。
    """
    for cid, v in verdicts.VERDICTS.items():
        assert v["verdict"] in ("refuted", "overstated"), f"{cid} 的裁決值不合法"
        for field in ("一句話", "推翻了什麼", "更正後"):
            assert v.get(field, "").strip(), f"{cid} 缺「{field}」"


def test_refuted_count_is_pinned(verdicts, index):
    """釘死數量。

    這條不是形式主義：裁決一旦無聲掉出索引，上面幾支都還會過（剩下的宣稱各自
    仍然自洽），只有總數會變。2026-08-03 那次就是這樣悄悄發生的。

    數字變了要在這裡改，並且同時更新 record.html 的導言與報告的更正注記——
    刻意讓它變成一個要動三個地方的改動。
    """
    kinds = [v["verdict"] for v in verdicts.VERDICTS.values()]
    assert kinds.count("refuted") == 3, f"被推翻的條數變了：{kinds.count('refuted')}"
    assert kinds.count("overstated") == 3, f"說得太滿的條數變了：{kinds.count('overstated')}"
    assert len(index.CLAIMS) == 12, f"宣稱總數變了：{len(index.CLAIMS)}"
