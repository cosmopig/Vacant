"""CONFORM 臂（R440P 驗收閘門）的行為與收據鏈測試。

零 API 呼叫：用假 agent 餵固定程式碼，只跑本機沙箱與簽章鏈。
承重的三件事，壞掉就是機制壞掉：
  1. 早停——第一個通過可見驗收的就出貨，不多花呼叫；
  2. 拒交——五個都不過就 accepted=False（拒交是產品的一部分，不是失敗）；
  3. 收據可究責——每次嘗試都上鏈，改一個欄位就驗不過。
"""
from __future__ import annotations

import os
import random

import pytest

os.environ.setdefault(
    "VACANT_EVALPLUS_PATH", ".vacant-private/evalplus/MbppPlus-v0.2.0.jsonl.gz"
)

from ops.gain.gain_run import arm_conform  # noqa: E402
from vacant.codebench import EvalPlusMBPPLoader  # noqa: E402
from vacant.identity import Identity, PublicIdentity  # noqa: E402
from vacant.logbook import Logbook  # noqa: E402

GOOD = "def similar_elements(a, b):\n    return tuple(sorted(set(a) & set(b)))\n"
BAD = "def similar_elements(a, b):\n    return ()\n"


class _FakeAgent:
    def __init__(self, aid: str, code: str) -> None:
        self.agent_id, self._code = aid, code
        self.cost = self.market_cost = 0.0

    def generate(self, prompt, role=None, meta=None):  # noqa: D102
        return f"```python\n{self._code}\n```"


@pytest.fixture(scope="module")
def task():
    try:
        tasks = EvalPlusMBPPLoader(expose_contract=True).iter_tasks("x")
    except FileNotFoundError:
        pytest.skip("EvalPlus 官方包不在本機（VM 上才有），跳過")
    for t in tasks:
        if t["entry_point"] == "similar_elements":
            return t
    pytest.skip("找不到基準題")


def _run(task, codes, k=5):
    agents = [_FakeAgent(f"w{i}", c) for i, c in enumerate(codes)]
    book, ident, calls = Logbook(), Identity.generate(), [0]
    rng = random.Random(0)
    it = iter(agents)
    rng.choice = lambda seq: next(it)          # 固定指派順序，讓斷言可讀
    code, worker, involved, extra = arm_conform(task, agents, rng, calls, book, ident, k=k)
    return extra, calls[0], worker, book, ident


def test_early_stop_on_first_conforming_draft(task):
    extra, calls, worker, book, ident = _run(task, [GOOD, BAD, BAD, BAD, BAD])
    assert extra["accepted"] is True
    assert calls == 1, "第一個就通過可見驗收，不該再花呼叫"
    assert worker == "w0"
    assert book.verify_chain(PublicIdentity(ident.vacant_id, ident.pub))


def test_skips_non_conforming_and_names_who_failed(task):
    extra, calls, worker, book, ident = _run(task, [BAD, BAD, GOOD, GOOD, GOOD])
    assert extra["accepted"] is True and calls == 3 and worker == "w2"
    flags = [(a["worker"], a["visible_ok"]) for a in extra["conform_attempts"]]
    assert flags == [("w0", False), ("w1", False), ("w2", True)]


def test_refuses_when_no_draft_conforms(task):
    extra, calls, _worker, book, ident = _run(task, [BAD] * 5)
    assert extra["accepted"] is False, "五個都不過就要拒交"
    assert extra["visible_ok"] is False
    assert calls == 5, "拒交前要把預算用完，不能提早放棄"
    assert len(extra["conform_attempts"]) == 5
    assert book.verify_chain(PublicIdentity(ident.vacant_id, ident.pub))


def test_receipt_chain_detects_tampering(task):
    extra, _calls, _worker, book, ident = _run(task, [GOOD], k=1)
    who = PublicIdentity(ident.vacant_id, ident.pub)
    assert book.verify_chain(who)
    book.entries[0].payload["visible_ok"] = False      # 竄改收據
    assert not book.verify_chain(who), "改過的收據必須驗不過（究責的密碼學基礎）"


def test_budget_never_exceeds_k(task):
    for codes in ([BAD] * 5, [GOOD] * 5, [BAD, GOOD, BAD, BAD, BAD]):
        _extra, calls, _w, _b, _i = _run(task, codes)
        assert calls <= 5, "CONFORM 的呼叫上限必須與 OFF5 相同"


# round639：收據要說得出「卡在第幾條驗收」。`meets_demand` 的 err 是常數字串
# （每個失敗候選都是 "sandbox_check_failed"），所以這個欄位若壞掉會**安靜地**
# 退化成一片相同的訊息，而 R440P §六 對外那句話正是靠它。這裡釘死條號。
_STALL_AT_3 = ("def similar_elements(a, b):\n"
               "    if 11 in a: return ()\n"
               "    return tuple(sorted(set(a) & set(b)))\n")
_STALL_AT_2 = ("def similar_elements(a, b):\n"
               "    if 1 in a: return ()\n"
               "    return tuple(sorted(set(a) & set(b)))\n")


def test_receipt_names_which_acceptance_test_each_worker_stalled_on(task):
    extra, calls, worker, _book, _ident = _run(
        task, [_STALL_AT_3, _STALL_AT_2, GOOD], k=3)
    a = extra["conform_attempts"]
    assert extra["accepted"] and worker == "w2" and calls == 3
    assert [x["first_failing_test"] for x in a[:2]] == [3, 2], a
    assert all(x["n_visible_tests"] == 3 and x["loads_ok"] for x in a[:2]), a
    assert all(x["detail_reason"] is None for x in a[:2]), a
    # 通過者不算條號（省沙箱執行），所以不該有這些欄位
    assert "first_failing_test" not in a[2], a[2]


# ── round639 的收據細節（「卡在第幾條」）——釘住，別再退回常數字串 ──────────
#
# R440P §六 對外那句「收據列出各自卡在第幾條」原本沒有實作支撐：
# `meets_demand` 失敗一律回同一個常數 "sandbox_check_failed"。round639 補上切片器。
# 這幾個測試是那句話的**實作證據**，不是裝飾——它們一旦失敗，那句對外宣稱就不能講。

_BASE = "def similar_elements(a, b):\n    r = tuple(sorted(set(a) & set(b)))\n"


def _first_fail(task, src):
    extra, _c, _w, _b, _i = _run(task, [src], k=1)
    return extra["conform_attempts"][0]


def test_receipt_reports_which_visible_test_failed(task):
    """索引必須真的隨「哪一條先失敗」而變，不是恆為 1。"""
    # 三條可見測資的交集分別含 5 / 含 3 / 最大值 14
    got = [
        _first_fail(task, _BASE + "    return () if 5 in r else r\n")["first_failing_test"],
        _first_fail(task, _BASE + "    return () if 3 in r else r\n")["first_failing_test"],
        _first_fail(task, _BASE + "    return () if r and max(r) > 10 else r\n")["first_failing_test"],
    ]
    assert got == [1, 2, 3], f"收據的失敗索引沒有隨測資變：{got}"


def test_receipt_separates_load_failure_from_test_failure(task):
    """載都載不進去，跟跑到第幾條才錯，是兩種不同的事，收據要分得開。"""
    broken = _first_fail(task, "def similar_elements(a, b)\n    return ()\n")   # 語法錯
    assert broken["loads_ok"] is False
    assert broken["first_failing_test"] is None
    assert broken["detail_reason"] == "fails_before_any_test"

    wrong = _first_fail(task, _BASE + "    return ()\n")
    assert wrong["loads_ok"] is True and wrong["first_failing_test"] == 1


def test_receipt_stays_quiet_when_the_draft_conforms(task):
    """通過的候選不該被算失敗細節——那是多餘的沙箱執行。"""
    ok = _first_fail(task, _BASE + "    return r\n")
    assert ok["visible_ok"] is True
    # 通過時整組失敗細節根本不寫進收據（不是寫成 None）——省掉的是沙箱執行
    assert "first_failing_test" not in ok and "n_visible_tests" not in ok
