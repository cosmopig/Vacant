"""EQ5 臂（R446 等預算臂）的行為測試。

零 API 呼叫：假 agent 餵固定程式碼，只跑本機沙箱與簽章鏈。

EQ5 承重的是**等預算**這件事本身（LOOP_PROMPT 鐵律 1）。壞掉就是宣稱作廢：
  1. **預算恆為 k**——不早停，閘門與多數決花的是同一組 5 次呼叫；
  2. **閘門選擇與 `arm_conform` 逐字元相同**（差別只在花幾次呼叫，不在選到誰）；
  3. **多數決選擇與 `arm_off5` 逐字元相同**（同 seed ⇒ 同 rng 消耗順序 ⇒ 可精確比對）；
  4. 拒交仍然存在（多數決永不拒交，兩條規則因此可能交出不同東西）；
  5. 收據可究責。
"""
from __future__ import annotations

import os
import random

import pytest

os.environ.setdefault(
    "VACANT_EVALPLUS_PATH", ".vacant-private/evalplus/MbppPlus-v0.2.0.jsonl.gz"
)

from ops.gain.gain_run import arm_conform, arm_eq5, arm_off5  # noqa: E402
from vacant.codebench import EvalPlusMBPPLoader  # noqa: E402
from vacant.identity import Identity, PublicIdentity  # noqa: E402
from vacant.logbook import Logbook  # noqa: E402

GOOD = "def similar_elements(a, b):\n    return tuple(sorted(set(a) & set(b)))\n"
GOOD2 = ("def similar_elements(a, b):\n"
         "    out = [x for x in set(a) if x in set(b)]\n"
         "    return tuple(sorted(out))\n")
BAD = "def similar_elements(a, b):\n    return ()\n"
BAD2 = "def similar_elements(a, b):\n    return tuple()\n"

SEED = "eq5-fixture-2"   # 這顆 seed 抽到的候選裡有兩個不同的通過者、首尾不同——
                         # 「閘門挑第一個通過的」這件事才是可證偽的
                         # （夾具自檢見 ops/gain/eq5_mutation_check.py:_fixture_ok）


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


def _fixed_order(codes):
    """指派順序固定成 codes 的順序（讀斷言用），與 _run_real 的隨機指派分開。"""
    agents = [_FakeAgent(f"w{i}", c) for i, c in enumerate(codes)]
    rng = random.Random(0)
    it = iter(agents)
    rng.choice = lambda seq: next(it)
    return agents, rng


def _run_eq5_fixed(task, codes, k=5):
    agents, rng = _fixed_order(codes)
    book, ident, calls = Logbook(), Identity.generate(), [0]
    # 多數決那兩次 rng.choice 也會吃到 iterator，所以固定順序版只用來驗閘門側；
    # 給它多備幾個 agent，避免 StopIteration。
    it = iter(agents + agents)
    rng.choice = lambda seq: next(it) if seq is agents else seq[0]
    code, worker, involved, extra = arm_eq5(
        task, agents, rng, calls, book, ident, k=k)
    return code, worker, extra, calls[0], book, ident


def test_budget_is_always_k_even_when_first_draft_conforms(task):
    """等預算的定義就在這條：第一個就通過，仍然花滿 5 次呼叫。"""
    _code, worker, extra, calls, _b, _i = _run_eq5_fixed(
        task, [GOOD, BAD, BAD, BAD, BAD])
    assert calls == 5, "EQ5 不早停——它跟 OFF5 花一樣多的呼叫才叫等預算"
    assert extra["accepted"] is True and worker == "w0"
    assert extra["gate_calls_if_early_stopped"] == 1, "早停會花幾次是紀錄，不是預算"
    assert len(extra["conform_attempts"]) == 5, "五份候選都要驗收並上鏈"


def test_refuses_when_no_draft_conforms_but_vote_still_ships(task):
    _code, _worker, extra, calls, _b, _i = _run_eq5_fixed(task, [BAD] * 5)
    assert extra["accepted"] is False and calls == 5
    assert extra["vote_accepted"] is True, "多數決永不拒交——這正是兩條規則的差別"
    assert extra["vote_visible_ok"] is False


def test_gate_selection_is_identical_to_arm_conform(task):
    """同一組候選、同一個 seed ⇒ 閘門選到的碼與 `arm_conform` 逐字元相同。"""
    codes = [BAD, BAD2, GOOD, GOOD2, BAD]
    agents = [_FakeAgent(f"w{i}", c) for i, c in enumerate(codes)]

    c_code, c_worker, _inv, _ex = arm_conform(
        task, agents, random.Random(SEED), [0], Logbook(), Identity.generate())
    e_code, e_worker, _inv2, extra = arm_eq5(
        task, agents, random.Random(SEED), [0], Logbook(), Identity.generate())
    assert (e_code, e_worker) == (c_code, c_worker)
    assert extra["gate_code_sha256"] != ""


def test_vote_selection_is_identical_to_arm_off5(task):
    """同一組候選、同一個 seed ⇒ 多數決選到的碼與 `arm_off5` 逐字元相同。

    兩支對 rng 的消耗順序相同（5 次 choice(agents) → choice(tied) → choice(win)），
    所以這是精確比對，不是統計相似。
    """
    codes = [BAD, BAD2, GOOD, GOOD2, BAD]
    agents = [_FakeAgent(f"w{i}", c) for i, c in enumerate(codes)]

    o_code, o_worker, _inv, o_extra = arm_off5(
        task, agents, random.Random(SEED), [0])
    _e_code, _e_worker, _inv2, e_extra = arm_eq5(
        task, agents, random.Random(SEED), [0], Logbook(), Identity.generate())
    assert e_extra["vote_code"] == o_code
    assert e_extra["vote_worker"] == o_worker
    assert e_extra["vote_n_agree"] == o_extra["vote_agreement"]
    assert e_extra["vote_n_buckets"] == o_extra["n_buckets"]


def test_two_rules_can_disagree_on_the_same_candidates(task):
    """對比存在：多數是錯的、閘門挑得出對的那一份 ⇒ same_choice=False。"""
    codes = [BAD, BAD2, BAD, GOOD, BAD]
    agents = [_FakeAgent(f"w{i}", c) for i, c in enumerate(codes)]
    _code, _worker, _inv, extra = arm_eq5(
        task, agents, random.Random(SEED), [0], Logbook(), Identity.generate())
    assert extra["accepted"] is True, "有一份通過可見驗收，閘門要挑到它"
    assert extra["same_choice"] is False
    assert extra["vote_visible_ok"] is False, "多數（空 tuple）不該通過可見驗收"


def test_receipt_chain_verifies_and_names_every_attempt(task):
    _code, _worker, extra, _calls, book, ident = _run_eq5_fixed(
        task, [BAD, GOOD, BAD, BAD, BAD])
    assert book.verify_chain(PublicIdentity(ident.vacant_id, ident.pub))
    kinds = [e.type for e in book.entries]
    assert kinds == ["eq5_attempt"] * 5 + ["eq5_verdict"]
    assert extra["receipt_head"] == book.head()
