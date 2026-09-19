"""V/GT canary：把唯一標記種進 GT 側，掃**六條臂實際送出去的每一則文字**。

這支在架構裡承重什麼
────────────────────
`harness_vgt_audit.py` 是**事後**稽核（跑在已經落盤的 `calls.jsonl` 上），
它只看得到已經跑過的 run。這一支是**事前**的可執行防呆：直接呼叫
`gain_run` 的六條臂 ＋ `calibrate_pool`，把唯一標記種在 `hidden_check`
（＝GT 側）裡，然後斷言那個標記一次都沒有出現在送出的 `prompt` 或 `system`。
形狀照抄 `tests/test_x1_evalplus.py::test_gt_canary_never_leaks_to_model_side`。

兩者是互補的，不是重複：
  · 稽核掃的是**歷史**（可能漏掉還沒跑過的路徑）；
  · canary 掃的是**程式碼路徑**（不管有沒有 run 跑過它）。
round534 那個洞（稽核只掃 H 臂）之所以能躲這麼久，正是因為只有事後那一半。

⚠ **`assert sent`** 那一句不准刪：一則 prompt 都沒送出的情況下，
  「掃描零命中」是**真的**，但它證明的是量具沒接上，不是沒有洩漏。
  那是 `UNVERIFIABLE ≠ CLEAN` 的可執行版本。

⚠ 每一條正向斷言都配一條**負向控制**（故意把 canary 塞進 prompt，測試必須翻紅）。
  沒有負控的「掃描零命中」跟把掃描關掉在輸出上同形。

零 API 呼叫、零機時：agent 是本檔自己的假 agent，只跑本機沙箱。
"""
from __future__ import annotations

import random

import pytest

from ops.gain.gain_run import (arm_conform, arm_eq5, arm_off,  # noqa: E402
                               arm_off5, arm_on, arm_onr, calibrate_pool)
from vacant.identity import Identity  # noqa: E402
from vacant.logbook import Logbook  # noqa: E402

#: 唯一標記。兩個形狀各擋一種洩漏：字串（註解／訊息）與數值（測資字面值）。
GT_CANARY = "CANARY_GT_9f3c7e"
NUM_CANARY = "424242424242"

ARMS = ("OFF", "OFF5", "CONFORM", "EQ5", "ON", "ONR")

GOOD = "def solve(x):\n    return x + 1\n"
BAD = "def solve(x):\n    return x\n"


def _task(*, leak_into_prompt: bool = False) -> dict:
    """一題最小任務。canary **只**在 `hidden_check`，其餘欄位一個字都沒有。

    `leak_into_prompt=True` 是負向控制用的變體：同一顆 canary 出現在題目敘述裡
    ⇒ 掃描必須翻紅。它證明的是「這支測試真的在掃」，不是題庫有問題。
    """
    prompt = "define solve(x) returning x + 1"
    if leak_into_prompt:
        prompt += f"\n# hint {GT_CANARY}: solve({NUM_CANARY}) must work"
    return {
        "task_id": "canary-1",
        "prompt": prompt,
        "entry_point": "solve",
        "behavior_inputs": [[1], [5]],
        "input_contract": "assert isinstance(x, int), 'invalid inputs'",
        "visible_check": {"code": "assert solve(1) == 2"},
        # ── GT 側：canary 就種在這裡（一個註解 ＋ 一條真的隱藏測資）───────
        "hidden_check": {"code": (
            "assert solve(1) == 2\n"
            "assert solve(-1) == 0\n"
            f"# {GT_CANARY}\n"
            f"assert solve({NUM_CANARY}) == {int(NUM_CANARY) + 1}\n")},
    }


class RecordingAgent:
    """記下**每一次** `generate()` 的 `prompt` 與 `system`。

    ⚠ 兩個都要記：v2 稽核的 (c) 三條豁免對 `system` 一格都不給，
      理由是 persona 文字沒有回聲的理由——同一個理由在這裡是
      「system 也是送出去的文字」。只掃 prompt 會漏掉一整個通道。
    """

    def __init__(self, agent_id: str, code: str, model: str,
                 sent: list[tuple[str, str | None, str | None]]) -> None:
        self.agent_id, self._code, self.model = agent_id, code, model
        self.sent = sent
        self.cost = self.market_cost = 0.0

    def generate(self, prompt, *, role="gen", meta=None, system=None,
                 timeout_s=None, retries=None):
        self.sent.append((prompt, system, role))
        if role == "review":
            # 失敗票 ＋ 可解析的反例：讓 arm_on 走完
            # verify_review_counterexample → counterexample_check → revise
            # 那一整條（那是 harness 自己組字串最多的一段）。
            return ("VERDICT: FAIL\nCONCERN: off by one\n"
                    "TEST_ARGS: [1]\nEXPECTED: 2")
        return f"```python\n{self._code}```"


def _pool(sent) -> list[RecordingAgent]:
    """異質池：一好一壞、兩個 model family ⇒ `_diverse_reviewers`／
    `_independent_reviser` 都有東西可挑，ON 的五通呼叫才會全部走到。"""
    return [RecordingAgent("good-1", GOOD, "alpha/x", sent),
            RecordingAgent("bad-1", BAD, "beta/y", sent),
            RecordingAgent("good-2", GOOD, "beta/y", sent),
            RecordingAgent("bad-2", BAD, "alpha/x", sent)]


def _run_arm(arm: str, task: dict, seed: int,
             sent: list[tuple[str, str | None, str | None]]) -> None:
    """跑一條臂一次。回傳值不重要——這支測的是**送出去的文字**。"""
    agents = _pool(sent)
    rng = random.Random(seed)
    calls = [0]
    rep = {a.agent_id: {"n": 0, "ok": 0} for a in agents}
    if arm == "OFF":
        arm_off(task, agents, rng, calls)
    elif arm == "OFF5":
        arm_off5(task, agents, rng, calls)
    elif arm == "CONFORM":
        arm_conform(task, agents, rng, calls, Logbook(), Identity.generate())
    elif arm == "EQ5":
        arm_eq5(task, agents, rng, calls, Logbook(), Identity.generate())
    elif arm == "ON":
        arm_on(task, agents, rng, calls, rep, audit_rate=1.0)
    elif arm == "ONR":
        arm_onr(task, agents, rng, calls, rep, audit_rate=1.0)
    else:                                                    # pragma: no cover
        raise AssertionError(f"未知的臂 {arm}——名單漂掉了就不是在測六條臂")


def _hits(sent) -> list[tuple[str, str]]:
    """送出的文字裡命中 canary 的地方（`(哪一格, 摘錄)`）。"""
    out: list[tuple[str, str]] = []
    for prompt, system, role in sent:
        for where, text in (("prompt", prompt), ("system", system)):
            if not isinstance(text, str):
                continue
            for needle in (GT_CANARY, NUM_CANARY):
                if needle in text:
                    i = text.find(needle)
                    out.append((f"{role}:{where}", text[max(0, i - 60):i + 60]))
    return out


# ── sanity：canary 真的只在 GT 側 ────────────────────────────────────────
def test_canary_is_in_the_hidden_check_and_nowhere_else():
    t = _task()
    hidden = t["hidden_check"]["code"]
    assert GT_CANARY in hidden and NUM_CANARY in hidden
    for field in (t["prompt"], t["visible_check"]["code"], t["entry_point"],
                  t["input_contract"], repr(t["behavior_inputs"])):
        assert GT_CANARY not in field and NUM_CANARY not in field, field


# ── 正向：六條臂逐臂零命中 ──────────────────────────────────────────────
@pytest.mark.parametrize("arm", ARMS)
def test_gt_canary_never_reaches_the_model_side(arm):
    sent: list[tuple[str, str | None, str | None]] = []
    for seed in (0, 1, 2):
        # 三顆 seed：指派是隨機的，一顆 seed 只走到一部分分支
        # （CONFORM 早停與否、ON 修訂選哪一版）。
        _run_arm(arm, _task(), seed, sent)
    assert sent, "一則 prompt 都沒送出 ⇒ 量具沒接上，不是通過"
    assert not _hits(sent), _hits(sent)[:3]


def test_gt_canary_never_reaches_the_model_side_in_calibrate_pool(tmp_path):
    """`calibrate_pool` → `run_one`（`gain_run.py:1275`）也是一條送 prompt 的路徑。

    它不在 `--arms` 的名單上，所以很容易被「六條臂都掃過了」漏掉——
    而它用的是**同一份** `task["prompt"]`，並且拿 `hidden_check` 直接計分。
    """
    sent: list[tuple[str, str | None, str | None]] = []
    agents = _pool(sent)
    rows = tmp_path / "calibration.jsonl"
    result = calibrate_pool([_task()], agents, rows)
    assert sent, "一則 prompt 都沒送出 ⇒ 量具沒接上，不是通過"
    assert not _hits(sent), _hits(sent)[:3]
    # 落盤那一份也掃一次：`err` 照設計是常數字串，真的漏了就會在這裡現形。
    text = rows.read_text(encoding="utf-8")
    assert GT_CANARY not in text and NUM_CANARY not in text
    assert result["used_for_routing"] is False


# ── 負向控制：掃描本身要有牙齒 ──────────────────────────────────────────
@pytest.mark.parametrize("arm", ARMS)
def test_negative_control_the_scan_goes_red_when_the_canary_is_in_the_prompt(arm):
    """故意把 canary 塞進題目敘述 ⇒ 同一支掃描必須翻紅。

    抓不到就代表上面那條「零命中」是空的——掃描沒有掃到送出去的文字。
    """
    sent: list[tuple[str, str | None, str | None]] = []
    _run_arm(arm, _task(leak_into_prompt=True), 0, sent)
    assert sent
    hits = _hits(sent)
    assert hits, f"{arm}：canary 明明在 prompt 裡卻掃不到 ⇒ 掃描沒接上送出的文字"
    assert any(w.endswith(":prompt") for w, _ in hits)


def test_negative_control_the_scan_goes_red_on_a_planted_system_prompt():
    """system 那一格也要真的被掃到（只掃 prompt 會漏一整個通道）。"""
    sent = [("harmless", f"you are a coder. remember {GT_CANARY}", "gen")]
    hits = _hits(sent)
    assert hits and hits[0][0] == "gen:system"


def test_negative_control_calibrate_pool_scan_has_teeth(tmp_path):
    sent: list[tuple[str, str | None, str | None]] = []
    agents = _pool(sent)
    calibrate_pool([_task(leak_into_prompt=True)], agents,
                   tmp_path / "calibration.jsonl")
    assert _hits(sent), "canary 在 prompt 裡卻掃不到 ⇒ calibrate_pool 這一格沒接上"
