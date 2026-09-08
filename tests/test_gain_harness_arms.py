"""H 臂（HPI／HOC／HMIX）的行為、協定與 V/GT 測試——**全部零 API 呼叫**。

規格：`docs/HARNESS_STUDY_2026-09-07.md` §4.6 的 T1–T12，另加 D4（取碼器政策）
與 `entry_point_missing` 單獨計數。

假 agent 只實作 `chat(messages, …) -> (text, info)`，真的跑的是本機沙箱
（`vacant/checks.py` 的受限 worker）與簽章鏈——所以這些測試驗的是**機制**，
不是 mock 自己。題目用 LCB v2 的 `lcb_3634`（規格 §3.1／§3.2 的實跑用例就是它），
拿不到題庫就 skip，不假裝通過。

承重的三件事，壞掉就是機制壞掉：
  1. 迴圈真的會因為「跑出來的失敗訊息」而改（T2）——那是本實驗的處理本身；
  2. 拒交語意與 `arm_conform` 逐字同義（T3）——否則六條臂的 `leaked` 不可比；
  3. 送出去的文字裡沒有 GT（T6）——破了就整個 run 作廢。
"""
from __future__ import annotations

import hashlib
import inspect
import json
import pathlib
import random

import pytest

from ops.gain import gain_run
from ops.gain.brain_cline import ClineBrain
from ops.gain.gain_run import _GAIN_ALLOWED_IMPORTS, extract_code
from ops.gain.harness_arms import (DOOM_NUDGE, HARNESS_BUDGET,
                                   PROMPT_TRUNCATED_RETRY, extract_code_revision,
                                   flatten_messages, parse_selftests,
                                   precheck_detail, render_feedback,
                                   run_harness_arm, static_precheck,
                                   visible_report)
from ops.gain.harness_vgt_audit import (CODE_NEEDLES, hidden_only_needles,
                                        strip_frozen_constants)
from vacant.identity import Identity, PublicIdentity
from vacant.logbook import Logbook
from vacant.memory import KS1Violation, assert_ks1_clean

REPO = pathlib.Path(__file__).resolve().parents[1]

GOOD = """def calculateScore(s):
    from collections import defaultdict
    pos = defaultdict(list)
    total = 0
    for i, ch in enumerate(s):
        m = chr(ord('a') + (ord('z') - ord(ch)))
        if pos[m]:
            total += i - pos[m].pop()
        else:
            pos[ch].append(i)
    return total
"""
LOGIC_BAD = "def calculateScore(s):\n    return len(s)\n"       # AssertionError
EXC_BAD = "def calculateScore(s):\n    return s[999]\n"          # IndexError
LOOP_BAD = "def calculateScore(s):\n    while True:\n        pass\n"   # TimeoutError
IMPORT_BAD = "import os\ndef calculateScore(s):\n    return 0\n"       # forbidden_import
SYNTAX_BAD = "def calculateScore(s)\n    return 0\n"                   # syntax_error
NO_ENTRY = "def helper(s):\n    return 0\n"                            # entry_point_missing


def _const(n):
    return f"def calculateScore(s):\n    return {n}\n"


def _fence(code):
    return f"```python\n{code}\n```"


@pytest.fixture(scope="module")
def task():
    from vacant.codebench import LiveCodeBenchLoader
    try:
        tasks = list(LiveCodeBenchLoader(version="v2").iter_tasks("g-r440-lcb2"))
    except (FileNotFoundError, ValueError) as exc:      # pragma: no cover
        pytest.skip(f"LCB v2 題庫不在本機：{exc}")
    for t in tasks:
        if t["task_id"] == "lcb_3634":
            return t
    pytest.skip("找不到基準題 lcb_3634")


class _FakeAgent:
    """只實作 `chat`。`script` 是每輪的回應：str 或 {"text", "finish_reason"}。"""

    def __init__(self, aid: str, script: list) -> None:
        self.agent_id, self.script, self.i = aid, script, 0
        self.cost = self.market_cost = 0.0
        self.sent: list[list[dict]] = []

    def chat(self, messages, *, role="gen", meta=None, system=None,
             timeout_s=None, retries=None, turn=None, max_tokens=None):
        self.sent.append([dict(m) for m in messages])
        item = self.script[min(self.i, len(self.script) - 1)]
        self.i += 1
        if isinstance(item, str):
            item = {"text": item}
        text = item["text"]
        return text, {
            "finish_reason": item.get("finish_reason", "stop"),
            "usage": {"prompt_tokens": item.get("prompt_tokens", 10),
                      "completion_tokens": item.get("completion_tokens", 10),
                      "total_tokens": item.get("total_tokens", 20)},
            "model": "fake", "server_model": "fake", "latency_ms": 1,
        }


def _run(task, variant, script, *, budget=None, fence=True):
    """script 的元素是**程式碼**（自動包圍欄）或已經寫好的回應 dict／字串。"""
    prepared = []
    for item in script:
        if isinstance(item, str):
            prepared.append(_fence(item) if fence else item)
        else:
            prepared.append(item)
    agent = _FakeAgent("w0", prepared)
    rng = random.Random(0)
    rng.choice = lambda seq: agent          # 一題一個 worker，固定成 w0
    book, ident, calls = Logbook(), Identity.generate(), [0]
    bud = {"sandbox_timeout_s": 3}
    bud.update(budget or {})
    code, worker, involved, extra = run_harness_arm(
        task, [agent], rng, calls, book, ident, variant=variant,
        wire_mode="multiturn", budget=bud, allowed_imports=_GAIN_ALLOWED_IMPORTS)
    return {"code": code, "worker": worker, "involved": involved, "extra": extra,
            "calls": calls[0], "agent": agent, "book": book, "ident": ident}


# ── T1 早停 ──────────────────────────────────────────────────────────────
def test_t1_early_stop_when_first_draft_passes_visible(task):
    r = _run(task, "HPI", [GOOD])
    e = r["extra"]
    assert e["accepted"] is True and e["visible_ok"] is True
    assert e["harness_calls"] == 1 and r["calls"] == 1, "第一輪就過就不該再花呼叫"
    assert e["stop_reason"] == "visible_pass" and e["first_pass_turn"] == 1
    assert r["code"] == GOOD.strip()


# ── T2 修訂真的會發生（本實驗的處理本身）─────────────────────────────────
def test_t2_revision_happens_and_is_driven_by_the_execution_message(task):
    r = _run(task, "HPI", [LOGIC_BAD, GOOD])
    e = r["extra"]
    assert e["accepted"] is True and e["first_pass_turn"] == 2
    assert e["harness_turns"][0]["fail_kind"] == "assert"
    second_request = r["agent"].sent[1][-1]["content"]
    assert "AssertionError: args=['abcdef'] got=6 want=0" in second_request, \
        "第二輪送出去的必須是**執行結果原文**，不是摘要"
    assert "It did not pass" in second_request


# ── T3 拒交語意（必須與 arm_conform 逐字同義）───────────────────────────
def test_t3_refusal_returns_the_last_draft_like_arm_conform(task):
    r = _run(task, "HPI", [LOGIC_BAD] * 5)
    e = r["extra"]
    assert e["accepted"] is False and e["visible_ok"] is False
    assert e["stop_reason"] == "budget_calls"
    assert r["calls"] == HARNESS_BUDGET["max_calls"] == 5
    assert r["code"] == LOGIC_BAD.strip(), "拒交仍要回傳最後一份草稿（離線計分用）"
    assert set(("accepted", "visible_ok")) <= set(e)


# ── T4 四種 fail_kind ＋ 兩種 loader reason ──────────────────────────────
def test_t4_four_failure_kinds_and_two_distinct_loader_reasons(task):
    kinds = {}
    reasons = {}
    for name, code in (("logic", LOGIC_BAD), ("exc", EXC_BAD), ("loop", LOOP_BAD),
                       ("imp", IMPORT_BAD), ("syn", SYNTAX_BAD)):
        r = _run(task, "HPI", [code])
        t0 = r["extra"]["harness_turns"][0]
        kinds[name] = t0["fail_kind"]
        reasons[name] = t0["precheck_reason"]
    assert kinds == {"logic": "assert", "exc": "exception", "loop": "timeout",
                     "imp": "loader", "syn": "loader"}
    assert reasons["imp"] == "forbidden_import" and reasons["syn"] == "syntax_error"
    assert reasons["imp"] != reasons["syn"], "兩種 None 的成因必須分得開（§3.2）"


def test_t4b_loader_feedback_names_which_kind_and_which_symbol(task):
    r = _run(task, "HPI", [IMPORT_BAD, GOOD])
    msg = r["agent"].sent[1][-1]["content"]
    assert "The code could not be loaded: forbidden_import" in msg
    assert "(os)" in msg, "被擋的具體符號要說出來，否則是零資訊訊息"


# ── T5 static_precheck 不漂移（與沙箱同判準）────────────────────────────
_PRECHECK_CORPUS = [GOOD, LOGIC_BAD, EXC_BAD, LOOP_BAD, IMPORT_BAD, SYNTAX_BAD,
                    "def calculateScore(s):\n    return getattr(s, 'x')\n",
                    "from os import path\ndef calculateScore(s):\n    return 0\n",
                    "def calculateScore(s):\n    return s.__class__\n",
                    "import math\ndef calculateScore(s):\n    return math.floor(1.5)\n",
                    ""]


def test_t5_static_precheck_agrees_with_the_sandbox_loader():
    from vacant.checks import _candidate_functions
    for code in _PRECHECK_CORPUS:
        ok, reason = static_precheck(code, _GAIN_ALLOWED_IMPORTS, "calculateScore")
        sandbox_ok = _candidate_functions(
            code, allowed_imports=_GAIN_ALLOWED_IMPORTS,
            allowed_entry_points=("calculateScore",)) is not None
        assert ok == sandbox_ok, (code, reason, sandbox_ok)


def test_t5b_entry_point_missing_is_the_one_documented_one_way_difference():
    """`entry_point_missing` 是唯一允許的方向差：沙箱載得進去（拿不到 proxy 才炸），
    我們**提前**擋下來並單獨計數（D4）。方向反過來就是 bug。"""
    from vacant.checks import _candidate_functions
    ok, reason = static_precheck(NO_ENTRY, _GAIN_ALLOWED_IMPORTS, "calculateScore")
    assert (ok, reason) == (False, "entry_point_missing")
    assert _candidate_functions(
        NO_ENTRY, allowed_imports=_GAIN_ALLOWED_IMPORTS,
        allowed_entry_points=("calculateScore",)) is not None


def test_t5c_static_precheck_matches_the_sandbox_on_the_925_archived_r447_drafts():
    """r447 的 925 份真候選：0 分歧（本輪實跑，規格 §4.6-T5 引用的就是這個數字）。"""
    run = REPO / "runs" / "g_r447_conform_lcb2"
    if not (run / "calls.jsonl").exists():          # pragma: no cover
        pytest.skip("r447 歸檔不在本機")
    from vacant.checks import _candidate_functions
    entry = {}
    with (run / "rows.jsonl").open(encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            entry[row["task_id"]] = row.get("entry_point")
    n = divergences = 0
    refusals = {}
    with (run / "calls.jsonl").open(encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            arm = (rec.get("meta") or {}).get("arm")
            if not rec.get("ok") or arm not in ("OFF", "OFF5", "CONFORM"):
                continue
            ep = entry.get((rec.get("meta") or {}).get("task_id"))
            code = extract_code(rec["response"])
            n += 1
            ok, reason = static_precheck(code, _GAIN_ALLOWED_IMPORTS, ep)
            sandbox_ok = _candidate_functions(
                code, allowed_imports=_GAIN_ALLOWED_IMPORTS,
                allowed_entry_points=(ep,) if ep else ()) is not None
            divergences += int(ok != sandbox_ok)
            if not ok:
                refusals[reason] = refusals.get(reason, 0) + 1
    assert n == 925, f"語料份數變了（{n}）——引用的 0 分歧就不是同一件事了"
    assert divergences == 0
    assert refusals == {"forbidden_attr": 17, "syntax_error": 8}, refusals


# ── T6 回饋不含 GT ───────────────────────────────────────────────────────
def test_t6_no_ground_truth_in_anything_sent_to_the_model(task):
    r = _run(task, "HPI", [LOGIC_BAD, EXC_BAD, IMPORT_BAD, SYNTAX_BAD, LOGIC_BAD])
    needles, _skipped = hidden_only_needles(task)
    assert needles, "這題沒有『隱藏扣掉可見』的 case ⇒ 這個測試量不到東西"
    for messages in r["agent"].sent:
        for m in messages:
            scrubbed = strip_frozen_constants(m["content"])
            for needle in CODE_NEEDLES:
                assert needle not in scrubbed, (needle, m["content"][:200])
            for needle in needles:
                assert needle not in m["content"], (needle, m["content"][:200])


def test_t6b_harness_module_source_carries_no_ground_truth_identifiers():
    """§5.8 靜態斷言：模組全文不得出現驗收碼／隱藏測資專屬識別字。

    唯一的例外是給模型的那句禁令本身含 `exec(`（凍結常數，稽核腳本先扣掉）。
    """
    src = (REPO / "ops" / "gain" / "harness_arms.py").read_text(encoding="utf-8")
    for needle in ("hidden_check", "canonical", "__canon", "__aeq", "__tests",
                   "plus_input", "suitegauge", "_canonical_solutions"):
        assert needle not in src, needle
    assert "exec(" not in strip_frozen_constants(src)


# ── T7 KS-1 ──────────────────────────────────────────────────────────────
def test_t7_every_prompt_and_feedback_template_is_ks1_clean():
    import ops.gain.harness_arms as ha
    checked = 0
    for name in dir(ha):
        if name.startswith(("PROMPT_", "BLOCK_", "DOOM_", "FEEDBACK_", "SELFTEST_",
                            "FLATTEN_", "HMIX_")):
            value = getattr(ha, name)
            if isinstance(value, str):
                assert_ks1_clean(value)
                checked += 1
    assert checked >= 10, f"只檢查到 {checked} 個常數——名字規則可能漂移了"
    with pytest.raises(KS1Violation):                 # 負向控制：防呆真的會咬人
        assert_ks1_clean("You are responsible for the outcome.")


def test_t7b_rendered_feedback_is_ks1_clean(task):
    r = _run(task, "HMIX", [LOGIC_BAD, EXC_BAD])
    for messages in r["agent"].sent:
        for m in messages:
            assert_ks1_clean(m["content"])


# ── T8 收據可驗 ──────────────────────────────────────────────────────────
def test_t8_receipt_chain_verifies_and_detects_tampering(task):
    r = _run(task, "HPI", [LOGIC_BAD, GOOD])
    who = PublicIdentity(r["ident"].vacant_id, r["ident"].pub)
    assert r["book"].verify_chain(who)
    assert r["extra"]["receipt_head"] == r["book"].head()
    assert len(r["book"]) == 3, "兩輪 attempt ＋ 一筆 verdict"
    assert all(t["entry_hash"] for t in r["extra"]["harness_turns"])
    r["book"].entries[0].payload["fail_kind"] = "nocode"      # 竄改收據
    assert not r["book"].verify_chain(who), "改過的收據必須驗不過"


# ── T9 doom（只有 H-MIX 有）─────────────────────────────────────────────
def test_t9_hmix_nudges_once_then_stops_on_the_same_failure(task):
    r = _run(task, "HMIX", [LOGIC_BAD] * 5)
    e = r["extra"]
    assert e["stop_reason"] == "doom" and e["doom_triggered"] is True
    assert r["calls"] == 3, "第 2 輪同簽名 ⇒ 追加 nudge；第 3 輪還一樣 ⇒ 停"
    assert e["doom_nudges"] == 1
    assert DOOM_NUDGE in r["agent"].sent[2][-1]["content"]
    assert DOOM_NUDGE not in r["agent"].sent[1][-1]["content"]
    assert e["accepted"] is False


def test_t9b_the_other_two_arms_do_not_doom_on_the_same_input(task):
    for variant, script in (("HPI", [LOGIC_BAD] * 5),
                            ("HOC", ["SELFTEST: NONE"] + [LOGIC_BAD] * 4)):
        r = _run(task, variant, script, fence=(variant != "HOC"))
        e = r["extra"]
        assert e["stop_reason"] == "budget_calls", (variant, e["stop_reason"])
        assert e["doom_triggered"] is False and e["doom_nudges"] == 0
        assert all(DOOM_NUDGE not in m[-1]["content"] for m in r["agent"].sent)


def test_t9c_hmix_keeps_going_when_the_failure_changes(task):
    r = _run(task, "HMIX", [_const(1), _const(2), _const(3), _const(4), _const(6)])
    assert r["extra"]["stop_reason"] == "budget_calls"
    assert r["extra"]["doom_nudges"] == 0 and r["calls"] == 5


# ── T10 context 政策 ─────────────────────────────────────────────────────
def test_t10_context_policy_lengths(task):
    script = [_const(1), _const(2), _const(3), _const(4), _const(6)]
    hmix = _run(task, "HMIX", script)
    hpi = _run(task, "HPI", script)
    assert [len(m) for m in hmix["agent"].sent] == [1, 3, 3, 3, 3], \
        "HMIX 只留 [u1, a_{n-1}, u_n]"
    assert [len(m) for m in hpi["agent"].sent] == [1, 3, 5, 7, 9], "HPI 全留"
    fourth = hmix["agent"].sent[3]
    assert fourth[0]["content"] == hmix["agent"].sent[0][0]["content"]
    assert fourth[1]["role"] == "assistant" and _const(3) in fourth[1]["content"]


def test_t10b_flattened_wire_mode_sends_exactly_one_message(task):
    agent = _FakeAgent("w0", [_fence(_const(n)) for n in (1, 2, 3, 4, 6)])
    rng = random.Random(0)
    rng.choice = lambda seq: agent
    run_harness_arm(task, [agent], rng, [0], Logbook(), Identity.generate(),
                    variant="HPI", wire_mode="flattened",
                    budget={"sandbox_timeout_s": 3},
                    allowed_imports=_GAIN_ALLOWED_IMPORTS)
    assert [len(m) for m in agent.sent] == [1, 1, 1, 1, 1]
    later = agent.sent[3][0]["content"]
    assert "conversation to continue" in later, "攤平格式要刻意不像對話"
    assert "--- CURRENT REQUEST ---" in later and "--- REPLY 1 ---" in later


def test_t10c_flatten_leaves_a_single_message_untouched():
    one = [{"role": "user", "content": "hello"}]
    assert flatten_messages(one) == one


# ── T11 截斷保護 ─────────────────────────────────────────────────────────
def test_t11_truncated_output_is_not_used_and_is_asked_for_again(task):
    cut = {"text": "```python\ndef calculateScore(s):\n    tot", "finish_reason": "length"}
    r = _run(task, "HPI", [cut, GOOD])
    e = r["extra"]
    assert e["truncated_retries"] == 1 and e["accepted"] is True
    assert e["first_pass_turn"] == 2 and r["calls"] == 2
    t0 = e["harness_turns"][0]
    assert t0["kind"] == "truncated_retry" and t0["used_output"] is False
    assert t0["code_sha256"] is None, "截斷的輸出不得被當成草稿"
    assert PROMPT_TRUNCATED_RETRY in r["agent"].sent[1][-1]["content"]


def test_t11b_only_one_truncation_retry_then_the_output_is_used(task):
    cut = {"text": _fence(LOGIC_BAD), "finish_reason": "length"}
    r = _run(task, "HPI", [cut] * 5)
    e = r["extra"]
    assert e["truncated_retries"] == 1, "額度只有一次"
    kinds = [t["kind"] for t in e["harness_turns"]]
    assert kinds[0] == "truncated_retry" and "truncated_retry" not in kinds[1:]
    assert e["harness_turns"][1]["fail_kind"] == "assert", \
        "第二次再截斷就照常使用輸出（否則會無限重發）"


# ── T12 既有臂逐位不變 ───────────────────────────────────────────────────
# round460b 之前（HEAD 84d101d）量到的原始碼 sha256。這一張表是「順手改一下」
# 的防呆：H 臂只准**呼叫**這些函式，不准動它們一個字（§4.5 的不動清單）。
FROZEN_SOURCE_SHA = {
    "arm_off": "04e6c758a5fc36fbd6147170a21dc8ea6e29c9826935c2fedacd0b834158dd7b",
    "arm_off5": "01026c363851afe66a29a4f41ed3344a2eb579a331db4b6aeb3b85465d7b0447",
    "arm_conform": "b987a2fa000df9afbfddaf7d26b948bb095d732eaeb68b76ba18bfa3e28337fe",
    "arm_eq5": "c5eb88e69b8c2fa39f8ffc5f25c40a7740c03b685be837f516233dd771ba0719",
    "arm_on": "9f67066153ed4894e644c09535d4558d0242792ce86c1716ecb20cb901eeb23f",
    "arm_onr": "9f8d86e2700953127a039697b4162ecd4a4898a4a5b8853af045c7f84ccb092f",
    "extract_code": "869e6e2cb10c15e00a81e9d9ddaac57c8cd60c08abdd3f08323bbed6107150cd",
    "meets_demand": "0df188d5dd6626622e6cd6b44691937ae727700d74cb61d6fd85411678059b7e",
    "behavior_signature": "a5bc15ad665ef31873b50c920e7b7116c61eb682ffffd460f9529780111ad53a",
    "conform_failure_detail": "237992047d020e62ba1ea896aa88aa3992616f19f63d9ff4088b7508753206a0",
    "_visible_test_slicer": "e0efdd0277cf82401bb812936f16f88329b31697670d6eef4d9bd8eaef0f4178",
}
GENERATE_SHA = "130c47c565b8bbdf5f074898ef77b221b1f914059024c9a2717359aae54a111b"


def test_t12_existing_arms_and_generate_are_byte_identical():
    for name, want in FROZEN_SOURCE_SHA.items():
        src = inspect.getsource(getattr(gain_run, name))
        got = hashlib.sha256(src.encode("utf-8")).hexdigest()
        assert got == want, f"{name} 被改過了（{got}）——H 臂不准動既有臂"
    got = hashlib.sha256(
        inspect.getsource(ClineBrain.generate).encode("utf-8")).hexdigest()
    assert got == GENERATE_SHA, "generate() 必須逐位元不變（chat() 是**並存**的方法）"


def test_t12b_chat_exists_and_is_not_generate():
    assert callable(ClineBrain.chat) and ClineBrain.chat is not ClineBrain.generate
    sig = inspect.signature(ClineBrain.chat)
    for param in ("messages", "role", "meta", "timeout_s", "retries", "turn"):
        assert param in sig.parameters


# ── D4 取碼器政策 ────────────────────────────────────────────────────────
_TWO_BLOCKS = ("Here is what was wrong:\n\n```\nreturn len(s)\n```\n\n"
               "Fixed:\n\n```python\n" + GOOD + "```\n")


def test_d4_first_turn_uses_gain_run_extract_code_unchanged(task):
    r = _run(task, "HPI", [{"text": _TWO_BLOCKS}])
    t0 = r["extra"]["harness_turns"][0]
    assert t0["extractor"] == "gain_run.extract_code"
    assert t0["code_sha256"] == hashlib.sha256(
        extract_code(_TWO_BLOCKS).encode("utf-8")).hexdigest()
    assert t0["extractor_divergent"] is False


def test_d4_revision_turns_pick_the_first_parsing_block_that_defines_the_entry(task):
    r = _run(task, "HPI", [LOGIC_BAD, {"text": _TWO_BLOCKS}])
    e = r["extra"]
    assert e["accepted"] is True and e["first_pass_turn"] == 2
    t1 = e["harness_turns"][1]
    assert t1["extractor"] == "harness_first_valid" and t1["extractor_divergent"]
    assert e["extractor_divergences"] == 1
    assert t1["baseline_code_sha256"] != t1["code_sha256"], "兩個選擇都要落盤"


def test_d4_revision_falls_back_to_extract_code_when_no_block_qualifies(task):
    text = "```python\nnot python(((\n```"
    r = _run(task, "HPI", [LOGIC_BAD, {"text": text}])
    t1 = r["extra"]["harness_turns"][1]
    assert t1["extractor"] == "gain_run.extract_code"
    assert t1["extractor_divergent"] is False


def test_d4_extract_code_revision_unit():
    code, fallback = extract_code_revision(_TWO_BLOCKS, "calculateScore")
    assert code == GOOD.strip() and fallback is False
    code, fallback = extract_code_revision("no fences here", "calculateScore")
    assert fallback is True and code == "no fences here"


def test_d4_nocode_is_counted_and_answered_with_the_protocol_reminder(task):
    r = _run(task, "HPI", [{"text": "I would use a stack."}, GOOD])
    e = r["extra"]
    assert e["nocode_turns"] == 1 and e["harness_turns"][0]["fail_kind"] == "nocode"
    assert e["harness_turns"][0]["n_code_blocks"] == 0
    assert "No Python code block was found" in r["agent"].sent[1][-1]["content"]
    assert e["accepted"] is True, "協定失敗計入預算但不是拒交理由"


def test_d4_first_block_non_python_is_counted_separately(task):
    # 第一塊是 `return len(s)`（函式外的 return ⇒ 不是合法 Python），第二塊才是解答。
    r = _run(task, "HPI", [LOGIC_BAD, {"text": _TWO_BLOCKS}])
    assert r["extra"]["first_block_non_python"] == 1
    assert r["extra"]["harness_turns"][1]["first_block_non_python"] is True


def test_d4_entry_point_missing_is_counted_separately(task):
    r = _run(task, "HPI", [NO_ENTRY, GOOD])
    e = r["extra"]
    assert e["entry_point_missing"] == 1 and e["loader_refusals"] == 1
    assert e["harness_turns"][0]["precheck_reason"] == "entry_point_missing"
    assert "entry_point_missing" in r["agent"].sent[1][-1]["content"]


# ── H-OC 專屬：計畫輪與自測（模型的碼一行都不執行）──────────────────────
def test_hoc_plan_turn_costs_one_call_and_yields_selftests(task):
    plan = ("PLAN:\nuse a stack\nEDGE CASES:\nempty string\n"
            "SELFTEST: ['aczzx'] -> 5\nSELFTEST: ['abcdef'] -> 0\n")
    r = _run(task, "HOC", [{"text": plan}, GOOD])
    e = r["extra"]
    assert e["selftests_parsed"] == 2 and e["accepted"] is True
    assert e["harness_turns"][0]["kind"] == "plan"
    assert e["harness_turns"][1]["kind"] == "build"
    assert e["first_pass_turn"] == 2 and r["calls"] == 2
    assert "Now write the solution" in r["agent"].sent[1][-1]["content"]


def test_hoc_selftest_failure_is_labelled_as_the_models_own_and_maybe_wrong(task):
    plan = "PLAN:\nx\nEDGE CASES:\ny\nSELFTEST: ['abcdef'] -> 0\n"
    r = _run(task, "HOC", [{"text": plan}, LOGIC_BAD, GOOD])
    msg = r["agent"].sent[2][-1]["content"]
    assert "Your own test also failed" in msg
    assert "may itself be wrong" in msg and "you expected=0" in msg
    assert r["extra"]["harness_turns"][1]["selftests_failed"] == 1


def test_hoc_budget_is_five_calls_total_including_the_plan_turn(task):
    plan = "PLAN:\nx\nEDGE CASES:\ny\nSELFTEST: NONE\n"
    r = _run(task, "HOC", [{"text": plan}] + [LOGIC_BAD] * 5)
    assert r["calls"] == 5 and r["extra"]["stop_reason"] == "budget_calls"
    assert r["extra"]["n_turns"] == 5, "計畫輪要跟一次修訂機會競爭（§4.0.6）"


def test_parse_selftests_rejects_garbage_and_counts_it():
    cases, bad = parse_selftests(
        "SELFTEST: ['a'] -> 1\nSELFTEST: nonsense\nSELFTEST: NONE\n"
        "SELFTEST: ['a -> b'] -> 'x'\n")
    assert cases == [(["a"], 1), (["a -> b"], "x")]
    assert bad == 1


def test_selftest_rendering_never_executes_model_authored_code(task):
    """模型只能交 literal 對；渲染出來的檢查碼是 harness 自己的模板。"""
    from ops.gain.harness_arms import render_selftest_check
    src = render_selftest_check("calculateScore", [(["aczzx"], 5)], "deadbeef")
    assert "import" not in src and "open(" not in src
    assert "calculateScore(*__vst_a_deadbeef)" in src


# ── 其餘骨架 ─────────────────────────────────────────────────────────────
def test_one_worker_per_task_across_all_turns(task):
    r = _run(task, "HPI", [LOGIC_BAD, EXC_BAD, GOOD])
    assert r["worker"] == "w0" and r["involved"] == ["w0"]
    assert {t["agent_id"] for t in r["extra"]["harness_turns"]} == {"w0"}


def test_budget_stops_on_tokens_before_calls_run_out(task):
    r = _run(task, "HPI", [{"text": _fence(LOGIC_BAD), "total_tokens": 40_000}])
    assert r["extra"]["stop_reason"] == "budget_tokens" and r["calls"] == 1


def test_feedback_message_is_truncated_head_and_tail_but_logged_in_full():
    long = "args=" + "A" * 5000 + " want=Z"
    out = render_feedback("assert", {"message": long}, "HPI")
    assert "characters omitted" in out
    assert out.count("A") == 1990 + 8 or "AAAA" in out
    assert len(out) < 2600
    assert out.startswith("The function was run against the acceptance tests.")


def test_visible_report_classifies_the_five_documented_outcomes(task):
    assert visible_report(GOOD, task, 3)[0] == "pass"
    assert visible_report(LOGIC_BAD, task, 3)[1] == "AssertionError"
    assert visible_report(EXC_BAD, task, 3)[1] == "IndexError"
    assert visible_report(LOOP_BAD, task, 3)[1] == "TimeoutError"
    assert visible_report(IMPORT_BAD, task, 3) is None
    assert visible_report(SYNTAX_BAD, task, 3) is None


def test_precheck_detail_names_the_symbol():
    assert precheck_detail(IMPORT_BAD, _GAIN_ALLOWED_IMPORTS, "calculateScore") == "os"
    assert precheck_detail(
        "def calculateScore(s):\n    return getattr(s, 'x')\n",
        _GAIN_ALLOWED_IMPORTS, "calculateScore") == "getattr"


def test_rows_extra_carries_everything_the_offline_analysis_needs(task):
    r = _run(task, "HPI", [LOGIC_BAD, GOOD])
    for key in ("accepted", "visible_ok", "harness_variant", "harness_wire_mode",
                "harness_calls", "harness_tokens_total", "harness_wall_s",
                "stop_reason", "first_pass_turn", "n_turns", "loader_refusals",
                "nocode_turns", "truncated_retries", "doom_triggered",
                "receipt_head", "harness_turns"):
        assert key in r["extra"], key
    for key in ("turn", "kind", "agent_id", "finish_reason", "n_code_blocks",
                "code_sha256", "precheck_ok", "precheck_reason", "fail_kind",
                "fail_message_full_sha256", "n_visible_tests", "context_messages",
                "entry_hash"):
        assert key in r["extra"]["harness_turns"][0], key


# ── V/GT 動態稽核（§5.8）：要能抓到真的洩漏，不是只會說 CLEAN ─────────────
def _write_calls(tmp_path, records):
    (tmp_path / "calls.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n",
        encoding="utf-8")
    return tmp_path


def test_vgt_audit_passes_on_a_real_harness_conversation(task, tmp_path):
    from ops.gain.harness_vgt_audit import audit_run
    r = _run(task, "HMIX", [LOGIC_BAD, EXC_BAD, SYNTAX_BAD, IMPORT_BAD, GOOD])
    records = [{"meta": {"arm": "HMIX", "task_id": task["task_id"]},
                "system": "你是一位程式設計師。", "messages": m}
               for m in r["agent"].sent]
    result = audit_run(_write_calls(tmp_path, records), {task["task_id"]: task})
    assert result["verdict"] == "CLEAN" and result["records_audited"] == 5
    assert result["violations"] == []


def test_vgt_audit_catches_a_planted_hidden_case_leak(task, tmp_path):
    """突變測試：把一個**只在隱藏側**的 case 塞進送出的文字 ⇒ 必須被抓到。"""
    from ops.gain.harness_vgt_audit import audit_run
    needles, _skipped = hidden_only_needles(task)
    leak = needles[0]
    records = [{"meta": {"arm": "HPI", "task_id": task["task_id"]},
                "system": "s", "messages": [
                    {"role": "user", "content": f"also make sure {leak} works"}]}]
    result = audit_run(_write_calls(tmp_path, records), {task["task_id"]: task})
    assert result["verdict"] == "VIOLATION"
    assert result["violations"][0]["rule"] == "hidden_case_leak"


def test_vgt_audit_catches_check_code_identifiers(task, tmp_path):
    from ops.gain.harness_vgt_audit import audit_run
    records = [{"meta": {"arm": "HOC", "task_id": task["task_id"]},
                "system": "s", "messages": [
                    {"role": "user", "content": task["visible_check"]["code"]}]}]
    result = audit_run(_write_calls(tmp_path, records), {task["task_id"]: task})
    assert result["verdict"] == "VIOLATION"
    assert {v["rule"] for v in result["violations"]} == {"check_code_identifier"}


def test_vgt_audit_refuses_to_pass_a_task_it_cannot_map(task, tmp_path):
    """對不到題目就不能說 CLEAN——「沒有檢查」不准冒充「沒有違規」。"""
    from ops.gain.harness_vgt_audit import audit_run
    records = [{"meta": {"arm": "HPI", "task_id": "lcb_does_not_exist"},
                "system": "s", "messages": [{"role": "user", "content": "hi"}]}]
    result = audit_run(_write_calls(tmp_path, records), {task["task_id"]: task})
    assert result["verdict"] == "VIOLATION"
    assert result["unknown_task_ids"] == ["lcb_does_not_exist"]


def test_allowed_import_whitelist_does_not_drift_from_the_runner():
    """不變量 5：H 臂用的白名單必須就是 `gain_run` 那一份（同一個沙箱規則）。"""
    from ops.gain.harness_arms import DEFAULT_ALLOWED_IMPORTS
    assert tuple(DEFAULT_ALLOWED_IMPORTS) == tuple(_GAIN_ALLOWED_IMPORTS)


def test_run_harness_arm_defaults_to_the_runner_whitelist(task):
    r = _run_default_whitelist(task)
    assert r["extra"]["harness_turns"][0]["precheck_reason"] == "forbidden_import"


def _run_default_whitelist(task):
    agent = _FakeAgent("w0", [_fence(IMPORT_BAD)])
    rng = random.Random(0)
    rng.choice = lambda seq: agent
    book, ident, calls = Logbook(), Identity.generate(), [0]
    code, worker, involved, extra = run_harness_arm(
        task, [agent], rng, calls, book, ident, variant="HPI",
        wire_mode="multiturn", budget={"sandbox_timeout_s": 3})
    return {"extra": extra}


# ── round460c：線路探針的三分法（這一組原本整組不存在，所以 smoke 才踩到）──
#
# 實測背景（2026-09-07，直連後端 1003，gemma-4-12b-it-qat）：四則訊息的 body
# 在 max_tokens=16／64 回 `finish_reason=length` ＋ **空 content**，256 才回 "OK"。
# 舊版探針寫死 16 ⇒ `EmptyResponse` ⇒ `InfraVoid` ⇒ 三條 H 臂逐題 infra_void、
# 零 row，而端點其實好好的。下面四條把那個死法釘住。
class _ProbeAgent:
    """只回應 `chat()` 的假 agent；`raises` 給定時就丟那個例外。"""

    def __init__(self, raises=None):
        self.agent_id = "probe-0"
        self.raises = raises
        self.kwargs: list[dict] = []

    def chat(self, messages, **kw):
        self.kwargs.append(kw)
        if self.raises is not None:
            raise self.raises
        return "OK", {"finish_reason": "stop", "usage": {"total_tokens": 3},
                      "model": "m", "server_model": "m", "latency_ms": 1}


def test_wire_probe_max_tokens_is_large_enough_for_a_reasoning_model():
    """16 是實測不夠的那個值：reasoning 先吃掉整個上限，content 交空白。"""
    from ops.gain.harness_arms import WIRE_PROBE_MAX_TOKENS, reset_wire_mode
    assert WIRE_PROBE_MAX_TOKENS >= 256, (
        "實測 gemma-4-12b-it-qat：16／64 回空 content，256 才回 OK")
    reset_wire_mode()
    agent = _ProbeAgent()
    from ops.gain.harness_arms import probe_wire_mode
    assert probe_wire_mode(agent) == "multiturn"
    assert agent.kwargs[0]["max_tokens"] == WIRE_PROBE_MAX_TOKENS
    reset_wire_mode()


def test_wire_probe_treats_empty_content_as_the_wire_being_accepted():
    """200 ＋ 空 content ＝ 形狀被接受了。判成「連不上」會讓整條臂全 void。"""
    from ops.gain.brain_cline import InfraVoid
    from ops.gain.harness_arms import probe_wire_mode, reset_wire_mode
    reset_wire_mode()
    err = InfraVoid("hasty-2 重試 2 次仍失敗：EmptyResponse: content 為空"
                    "（finish_reason=length，reasoning 47 字）")
    assert probe_wire_mode(_ProbeAgent(raises=err)) == "multiturn"
    reset_wire_mode()


def test_wire_probe_still_falls_back_to_flattened_on_400():
    from ops.gain.brain_cline import InfraVoid
    from ops.gain.harness_arms import probe_wire_mode, reset_wire_mode
    reset_wire_mode()
    err = InfraVoid("w 重試 2 次仍失敗：HTTPError: HTTP Error 400: Bad Request")
    assert probe_wire_mode(_ProbeAgent(raises=err)) == "flattened"
    reset_wire_mode()


def test_wire_probe_still_reraises_a_real_transport_failure():
    """瞬斷不准變成「實驗條件改變」——照拋，該格記 infra_void，下一題再探。"""
    from ops.gain.brain_cline import InfraVoid
    from ops.gain.harness_arms import probe_wire_mode, reset_wire_mode
    reset_wire_mode()
    err = InfraVoid("w 重試 4 次仍失敗：URLError: <urlopen error timed out>")
    with pytest.raises(InfraVoid):
        probe_wire_mode(_ProbeAgent(raises=err))
    from ops.gain.harness_arms import current_wire_mode
    assert current_wire_mode() is None, "拋出去之後不准留下已決定的模式"
    reset_wire_mode()


# ── round460d：每一個 HTTP 請求都要有界 ─────────────────────────────────
#
# 為什麼這一組必須存在（2026-09-07 R460 冒煙掛四小時換來的）：
#   `urlopen(timeout=…)` 綁的是 **socket 逾時（每次 recv），不是請求逾時**。
#   HMIX 第一通呼叫 `timeout_s=600` 卡在 `_read_status` 的 `poll()` 裡 4 小時 08 分，
#   而 calls.jsonl 一列都沒新增（失敗才落盤）——從外面看就是「整個 run 死了」。
#   下面三條把兩件事釘住：(a) 三條路徑都**真的**把 timeout 送進 urlopen；
#   (b) 探針有**自己的**短逾時；(c) socket 逾時失效時牆鐘護欄仍然收得了尾。
class _FakeResponse:
    def __init__(self, payload: dict):
        self._raw = json.dumps(payload).encode()

    def read(self, *a):
        return self._raw

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


_OK_PAYLOAD = {"model": "m", "usage": {"total_tokens": 3},
               "choices": [{"finish_reason": "stop",
                            "message": {"content": "OK"}}]}


def _brain(tmp_path, **kw):
    return ClineBrain("probe-0", "sys", key="", log_path=tmp_path / "calls.jsonl",
                      model="m", **kw)


def test_every_http_request_passes_a_positive_timeout(tmp_path, monkeypatch):
    """generate／chat／線路探針三條路徑都必須把 timeout 交給 urlopen。

    沒有 timeout 的 `urlopen` 會永遠等下去，而且**失敗才落盤** ⇒ 卡住的時候
    calls.jsonl 是空的，外面看不出來它還活著。
    """
    import urllib.request

    from ops.gain.harness_arms import (WIRE_PROBE_TIMEOUT_S, probe_wire_mode,
                                       reset_wire_mode)

    seen: list[dict] = []

    def fake_urlopen(req, *args, **kwargs):
        seen.append({"args": args, "kwargs": kwargs})
        return _FakeResponse(_OK_PAYLOAD)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    brain = _brain(tmp_path, timeout_s=600, retries=4)
    assert brain.generate("hi") == "OK"
    assert brain.chat([{"role": "user", "content": "hi"}])[0] == "OK"
    reset_wire_mode()
    assert probe_wire_mode(brain) == "multiturn"
    reset_wire_mode()

    assert len(seen) == 3, "三條路徑都要真的送出去"
    for i, call in enumerate(seen):
        assert not call["args"], "timeout 要用具名參數送，位置參數讀不出來"
        assert "timeout" in call["kwargs"], f"第 {i} 通呼叫沒有帶 timeout"
        assert call["kwargs"]["timeout"] > 0, f"第 {i} 通呼叫的 timeout 不是正數"
    assert seen[0]["kwargs"]["timeout"] == 600
    assert seen[1]["kwargs"]["timeout"] == 600
    assert seen[2]["kwargs"]["timeout"] == WIRE_PROBE_TIMEOUT_S


def test_wire_probe_has_its_own_short_timeout():
    """探針只要三個 token 的 OK（實測 1.9 s），不該繼承 600 s 的產碼預算。"""
    from ops.gain.harness_arms import (WIRE_PROBE_TIMEOUT_S, probe_wire_mode,
                                       reset_wire_mode)
    assert 0 < WIRE_PROBE_TIMEOUT_S <= 120, "探針逾時要短——壞掉就快點知道"
    reset_wire_mode()
    agent = _ProbeAgent()
    assert probe_wire_mode(agent) == "multiturn"
    assert agent.kwargs[0]["timeout_s"] == WIRE_PROBE_TIMEOUT_S
    reset_wire_mode()


def test_wall_clock_guard_bounds_a_request_whose_socket_timeout_never_fires(
        tmp_path, monkeypatch):
    """socket 逾時沒兌現時，牆鐘護欄要收尾——語意沿用既有的重試→InfraVoid。"""
    import time as _time
    import urllib.request

    from ops.gain import brain_cline

    def blocking_urlopen(req, *args, **kwargs):     # 假裝 OS 不理 timeout
        _time.sleep(30)
        raise AssertionError("護欄沒有動作")

    monkeypatch.setattr(urllib.request, "urlopen", blocking_urlopen)
    monkeypatch.setattr(brain_cline, "WALL_CLOCK_SLACK_S", 0)
    brain = _brain(tmp_path, timeout_s=1, retries=1)
    t0 = _time.time()
    with pytest.raises(brain_cline.InfraVoid) as exc:
        brain.chat([{"role": "user", "content": "hi"}])
    assert _time.time() - t0 < 10, "護欄沒有在牆鐘上限附近動作"
    assert "WallClockTimeout" in str(exc.value)
    rec = json.loads((tmp_path / "calls.jsonl").read_text().splitlines()[0])
    assert rec["ok"] is False and "WallClockTimeout" in rec["error"], \
        "護欄咬到的那一次也要逐字落盤（鐵律 3）"
    import signal
    assert signal.getsignal(signal.SIGALRM) in (signal.SIG_DFL, signal.SIG_IGN), \
        "護欄要把 SIGALRM 還回去"
