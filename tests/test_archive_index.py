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
    而裁決留在原地假裝還在管事。

    2026-09-07 起有第二種合法形狀：條目**自帶** `宣稱`（見 verdicts 模組
    docstring）。那種不算孤兒，因為它裁的那句話就在它自己身上；下一支測試
    改為要求它把 `宣稱`／`來源` 都帶齊。
    """
    ids = {c["id"] for c in index.CLAIMS}
    orphans = sorted(cid for cid, v in verdicts.VERDICTS.items()
                     if cid not in ids and not v.get("宣稱"))
    assert not orphans, f"裁決指向不存在的宣稱：{orphans}"


def test_self_describing_verdicts_carry_claim_and_source(verdicts):
    """自帶宣稱的條目要帶齊 `宣稱` 與 `來源`。

    這是上一支測試放行的代價要付的地方：宣稱本文離開了 `CLAIMS`，就必須在
    這裡被釘住，否則會出現「有裁決、但沒有人知道它在裁哪句話、依據是什麼」。
    """
    for cid, v in verdicts.VERDICTS.items():
        if not v.get("宣稱"):
            continue
        for field in ("宣稱", "來源", "一句話"):
            assert v.get(field, "").strip(), f"{cid} 缺「{field}」"


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
    legal = ("refuted", "overstated", "held", "no_effect", "unresolved")
    for cid, v in verdicts.VERDICTS.items():
        assert v["verdict"] in legal, f"{cid} 的裁決值不合法：{v['verdict']}"
        if v["verdict"] not in ("refuted", "overstated"):
            # held／no_effect／unresolved 沒有「原句是錯的」可言，但一定要有
            # 一句話；held 與 unresolved 另外要有「邊界」——那是它能講到哪裡
            # 的界線，網頁上照印（vacant-docs-web README §措辭紀律 3）。
            assert v.get("一句話", "").strip(), f"{cid} 缺「一句話」"
            if v["verdict"] in ("held", "unresolved") and v.get("宣稱"):
                assert v.get("邊界", "").strip(), f"{cid} 缺「邊界」"
            continue
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
    assert kinds.count("refuted") == 6, f"被推翻的條數變了：{kinds.count('refuted')}"
    assert kinds.count("overstated") == 4, f"說得太滿的條數變了：{kinds.count('overstated')}"
    assert kinds.count("held") == 10, f"判準成立的條數變了：{kinds.count('held')}"
    assert kinds.count("no_effect") == 1, f"無可分辨差異的條數變了：{kinds.count('no_effect')}"
    assert kinds.count("unresolved") == 1, f"同號未解析的條數變了：{kinds.count('unresolved')}"
    assert len(index.CLAIMS) == 20, f"索引裡的宣稱總數變了：{len(index.CLAIMS)}"
    # 網頁上那面牆＝索引裡的 20 條 ＋ 自帶宣稱的 8 條。兩個數字分開釘，
    # 因為「索引比網頁少」正是這一支測試存在的理由，不能讓它悄悄擴大。
    self_described = [cid for cid, v in verdicts.VERDICTS.items() if v.get("宣稱")]
    assert len(self_described) == 8, f"自帶宣稱的條數變了：{len(self_described)}"
    assert len(index.CLAIMS) + len(self_described) == 28
