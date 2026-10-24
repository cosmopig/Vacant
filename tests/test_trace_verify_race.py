"""verify() 撞上「活著的工作階段」：寫入端在「讀鏈」與「讀 head.json」之間插了一筆
（寫入端整段持鎖「鏈→head」，但 verify 的讀路徑不持鎖）——舊代碼把這判成 BROKEN
『truncated or replaced』，把健康鏈報成截短。2026-10-24 dogfood 時在實專案上抓到：
`vacant trace verify` 先 BROKEN、再 OK。

修法：head 領先尾巴時有限重讀（最多再讀兩次）——在寫的追加會在重讀後對上，
真截短／換尾每次重讀都對不上 ⇒ 仍 BROKEN。誠實邊界：三次都對不上 ⇒ 驗不成（非 PASS）。
"""
from __future__ import annotations

import json

import pytest

from vacant_network.intake import keys
from vacant_network.trace import recorder as R


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("VACANT_HOME", str(tmp_path / "vh"))
    keys.init_local()
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "data.csv").write_text("a,1\nb,2\n")
    return ws, R.Recorder(ws)


def _five_steps(rec):
    for i in range(5):
        rec.append("coverage", {"i": i})


def _racy_book_once(monkeypatch, drop_first_call=1):
    """第一次 `_book()` 少了最後 N 筆（讀者恰好在追加前讀完鏈），之後正常。"""
    real = R.Recorder._book
    state = {"calls": 0}

    def racy(self):
        state["calls"] += 1
        book, torn = real(self)
        if state["calls"] <= drop_first_call:
            return type(book)(book.entries[:-1]), torn
        return book, torn

    monkeypatch.setattr(R.Recorder, "_book", racy)
    return state


def test_verify_tolerates_an_append_between_chain_and_head_read(env, monkeypatch):
    ws, rec = env
    _five_steps(rec)
    _racy_book_once(monkeypatch)
    ok, why = rec.verify()
    assert ok, why


def test_verify_since_tolerates_the_same_race(env, monkeypatch):
    ws, rec = env
    _five_steps(rec)
    ev = rec.events()
    mark = {"seq": ev[-2]["seq"], "hash": ev[-2]["hash"]}   # 上次驗到 4/5
    _racy_book_once(monkeypatch)
    ok, why, new_mark = rec.verify_since(mark)
    assert ok, why
    assert new_mark == {"seq": ev[-1]["seq"], "hash": ev[-1]["hash"]}


def test_persistent_truncation_is_still_broken(env):
    """負對照：head 領先且**重讀仍領先**＝截短，不得被重讀洗白。"""
    ws, rec = env
    _five_steps(rec)
    head = json.loads((rec.dir / "head.json").read_text(encoding="utf-8"))
    assert head["seq"] == 6                                    # 創世＋五筆
    lines = rec.chain_path.read_bytes().splitlines(keepends=True)
    rec.chain_path.write_bytes(b"".join(lines[:-1]))          # 砍掉最後一筆、head.json 留 6
    ok, why = rec.verify()
    assert not ok and "head is entry 6" in why, why
    ok, why, _ = rec.verify_since(None)
    assert not ok and "head is entry 6" in why, why


def test_still_broken_if_three_reads_all_disagree(env, monkeypatch):
    """三次讀都對不上：驗不成（不給 PASS），但說明裡要留「可能還在寫、重跑」的出路。"""
    ws, rec = env
    _five_steps(rec)
    real = R.Recorder._book

    def always_short(self):
        book, torn = real(self)
        return type(book)(book.entries[:-1]), torn

    monkeypatch.setattr(R.Recorder, "_book", always_short)
    ok, why = rec.verify()
    assert not ok, why
    assert "re-run" in why, why
