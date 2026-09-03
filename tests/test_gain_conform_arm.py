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
