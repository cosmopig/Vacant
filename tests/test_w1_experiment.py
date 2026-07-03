"""W1 實驗基建覆蓋：auditor / router / memory（M0/M1/M2＋A4/KS-1 防呆）/
batch（斷點續跑＋看門狗）/ x1 harness（任務族＋oracle-lesson pilot 路徑）。
對應裁決 §3-B（W1 範圍）與 10 §3–§4。
"""

import pytest

from vacant.auditor import Auditor
from vacant.batch import RunLedger, Watchdog
from vacant.host import Host
from vacant.identity import Identity
from vacant.logbook import Logbook
from vacant.memory import (
    Episode, KS1Violation, MemoryManager, MemoryStream,
    assert_ks1_clean, lesson_leaks_test_data,
)
from vacant.router import Router
from vacant.substrate import EchoSubstrate
from vacant.x1 import (
    FAMILIES, ORACLE_LESSONS, make_pilot_tasks, run_x1, transfer_curve,
)


# === auditor =================================================================

def test_auditor_deterministic_sampling():
    a = Auditor(rate=0.5, seed="s")
    picks = [a.should_audit(f"t{i}") for i in range(200)]
    assert picks == [a.should_audit(f"t{i}") for i in range(200)]  # 同 seed 同結果
    assert 40 < sum(picks) < 160  # 大致落在 rate 附近
    assert Auditor(rate=1.0).should_audit("x")
    assert not Auditor(rate=0.0).should_audit("x")
    assert Auditor(rate=0.0).should_audit("x", forced=True)  # probation 強制


def test_auditor_provable_fault():
    a = Auditor(rate=1.0)
    check = {"type": "equals", "value": "42"}
    rec = a.audit(task_id="t", target_id="v", answer="41", check=check,
                  claimed_pass=True, ts_ms=1)
    assert rec.ran and rec.passed is False and rec.provable_fault
    ok = a.audit(task_id="t", target_id="v", answer="42", check=check,
                 claimed_pass=True, ts_ms=1)
    assert ok.passed and not ok.provable_fault
    skipped = Auditor(rate=0.0).audit(task_id="t", target_id="v", answer="41",
                                      check=check, claimed_pass=True, ts_ms=1)
    assert not skipped.ran and skipped.passed is None and not skipped.provable_fault


# === router（trust on/off 單開關）============================================

def test_router_toggle(tmp_path):
    h = Host(tmp_path, substrate=EchoSubstrate(p_base=1.0))
    h.mint("a", niches=["reverse"])
    h.mint("b", niches=["reverse"])
    r = Router(h.registry, trust_on=False)
    sid = EchoSubstrate().substrate_id
    off_pick = r.pick("reverse", sid, seed="t1")
    assert off_pick is not None
    assert r.pick("reverse", sid, seed="t1").vacant_id == off_pick.vacant_id  # off＝確定性隨機
    r.toggle(True)
    assert r.pick("reverse", sid) is not None  # on＝UCB


# === memory ==================================================================

def _stream() -> MemoryStream:
    idn = Identity.generate()
    return MemoryStream(Logbook(), idn)


def _ep(i, *, audited=True, lesson=None, outcome="pass"):
    return dict(
        task_id=f"t{i}", spec_digest="s", answer_digest="a", reviews=[],
        audit={"ran": True, "passed": outcome == "pass"} if audited else None,
        outcome=outcome, lesson=lesson, check=None, ts_ms=i,
    )


def test_memory_episodes_are_signed_on_chain():
    st = _stream()
    MemoryManager("M2").record(st, **_ep(1, lesson="教訓：邊界要先想"))
    assert len(st.logbook) == 1
    assert st.episodes()[0].task_id == "t1"
    from vacant.identity import PublicIdentity
    assert st.logbook.verify_chain(PublicIdentity(st.identity.vacant_id, st.identity.pub))


def test_m0_injects_nothing_m1_injects_raw():
    st = _stream()
    m2 = MemoryManager("M2")
    m2.record(st, **_ep(1, lesson="字串邊界教訓"))
    assert MemoryManager("M0").inject(st, "task") == ""
    m1_block = MemoryManager("M1").inject(st, "task")
    assert "t1" in m1_block  # 原文（含未蒸餾欄位）


def test_m2_only_uses_audited_lessons():
    st = _stream()
    m2 = MemoryManager("M2")
    m2.record(st, **_ep(1, audited=True, lesson="被審過的教訓 boundary"))
    m2.record(st, **_ep(2, audited=False, lesson="沒被審的日記 boundary"))
    block = m2.inject(st, "boundary task")
    assert "被審過的教訓" in block
    assert "沒被審的日記" not in block  # 「被審」是資格線（責任 vs 日記的分界）


def test_m2_budget_caps_block():
    st = _stream()
    m2 = MemoryManager("M2", budget_tokens=10)
    m2.record(st, **_ep(1, lesson="很長的教訓 " * 200))
    assert len(m2.inject(st, "task")) <= 10 * 4


def test_ks1_guard():
    with pytest.raises(KS1Violation):
        assert_ks1_clean("記住：你有責任把這題做對")
    assert assert_ks1_clean("字串邊界要先想") == "字串邊界要先想"


def test_a4_lesson_leak_guard():
    check = {"type": "run_python", "code": "assert solve('zebra_secret')=='terces_arbez'"}
    assert lesson_leaks_test_data("記得 zebra_secret 要反轉", check)   # 逐字測資 → 擋
    assert not lesson_leaks_test_data("字串反轉注意空字串", check)      # 坑型抽象 → 放行
    st = _stream()
    with pytest.raises(ValueError):
        MemoryManager("M2").record(st, **{**_ep(1, lesson="輸入 zebra_secret 時輸出反轉"),
                                          "check": check})


# === batch（B4）==============================================================

def test_run_ledger_resume(tmp_path):
    p = tmp_path / "runs.jsonl"
    led = RunLedger(p)
    assert not led.is_done("M2", "t1", 0)
    led.mark_done("M2", "t1", 0, {"passed": True})
    # 重啟（重新載入同一檔案）→ 自動跳過已完成格
    led2 = RunLedger(p)
    assert led2.is_done("M2", "t1", 0)
    assert not led2.is_done("M2", "t2", 0)
    assert led2.result("M2", "t1", 0)["passed"] is True


def test_run_ledger_tolerates_truncated_tail(tmp_path):
    p = tmp_path / "runs.jsonl"
    RunLedger(p).mark_done("M2", "t1", 0, {"passed": True})
    with p.open("a") as f:
        f.write('{"worker":"M2","task":"t2"')  # 崩潰截斷的尾行
    led = RunLedger(p)
    assert led.is_done("M2", "t1", 0) and led.corrupt_lines == 1


def test_watchdog_down_and_recover():
    calls = {"n": 0}
    wd = Watchdog("http://127.0.0.1:1", timeout=0.2,
                  on_down=lambda msg: calls.__setitem__("n", calls["n"] + 1))
    assert not wd.ping()
    assert not wd.wait_alive(retries=2, interval=0, _sleep=lambda s: None)
    assert calls["n"] == 2  # 開始等待＋等滿仍死


# === x1 harness ==============================================================

class OracleFollowerBrain:
    """測試腦：看到族 oracle 教訓才會答對（模擬「遷移存在」的世界）。

    答對＝輸出通過隱藏測試的正解；這裡用查表（每族變體的正解函式源碼）。"""

    SOLUTIONS = {
        "string_edge": {
            0: "def solve(s):\n    out=''\n    for c in s:\n        if not out or out[-1]!=c: out+=c\n    return out",
        },
    }

    def __init__(self):
        self.calls = 0

    def generate(self, prompt: str) -> str:
        self.calls += 1
        if ORACLE_LESSONS["string_edge"] in prompt:
            return "```python\n" + self.SOLUTIONS["string_edge"][0] + "\n```"
        return "```python\ndef solve(s):\n    return s\n```"  # 沒記憶＝天真錯解


def test_x1_pilot_tasks_deterministic():
    a = make_pilot_tasks(5)
    b = make_pilot_tasks(5)
    assert [t.task_id for t in a] == [t.task_id for t in b]
    assert len(a) == 15
    # 隱藏測資紀律：隱藏 asserts 不出現在 prompt
    for t in a:
        for line in t.check["code"].splitlines():
            assert line.strip() not in t.prompt


def test_x1_oracle_lesson_transfer(tmp_path):
    """oracle-lesson 條件下，族內第 2 題起應被教訓救起（遷移通道打通）。"""
    from vacant.x1 import make_family_sequence
    # 變體 0 每 5 題輪到一次；取 15 題 → 3 個變體 0 的實例（有正解表）
    tasks = [t for t in make_family_sequence("string_edge", 15)
             if t.variant_params["variant"] == 0]
    assert len(tasks) == 3
    st = _stream()
    brain = OracleFollowerBrain()
    recs = run_x1(brain, "M2", tasks, stream=st, oracle=True,
                  ledger=RunLedger(tmp_path / "l.jsonl"),
                  trace_path=tmp_path / "trace.jsonl")
    assert recs[0]["passed"] is False          # 第一題：沒記憶 → 錯
    assert all(r["lesson_written"] for r in recs if r["outcome"] != "infra_void")
    # 之後：M2 注入 oracle 教訓 → 對
    later = [r["passed"] for r in recs[1:]]
    assert any(later), f"oracle-lesson 都救不起來＝管線斷了：{recs}"
    curve = transfer_curve(recs)
    assert curve["string_edge"][0] == 0.0


def test_x1_m0_arm_never_gets_memory(tmp_path):
    from vacant.x1 import make_family_sequence
    tasks = [t for t in make_family_sequence("string_edge", 2)
             if t.variant_params["variant"] == 0]
    st = _stream()
    brain = OracleFollowerBrain()
    recs = run_x1(brain, "M0", tasks, stream=st, oracle=True)
    assert all(r["passed"] is False for r in recs)  # M0 永遠拿不到教訓 → 永遠錯
    assert all(r["memory_tokens"] == 0 for r in recs)


def test_x1_resume_skips_done(tmp_path):
    from vacant.x1 import make_family_sequence
    tasks = [t for t in make_family_sequence("string_edge", 2)
             if t.variant_params["variant"] == 0]
    led = RunLedger(tmp_path / "l.jsonl")
    st = _stream()
    brain = OracleFollowerBrain()
    run_x1(brain, "M2", tasks, stream=st, oracle=True, ledger=led)
    first_calls = brain.calls
    # 斷點續跑：同 ledger 重跑 → 0 次新生成
    run_x1(brain, "M2", tasks, stream=_stream(), oracle=True,
           ledger=RunLedger(tmp_path / "l.jsonl"))
    assert brain.calls == first_calls


def test_x1_infra_void_on_persistent_failure(tmp_path):
    from vacant.x1 import make_family_sequence

    class DeadBrain:
        def generate(self, prompt):
            raise ConnectionError("端點掛了")

    tasks = make_family_sequence("string_edge", 1)
    recs = run_x1(DeadBrain(), "M0", tasks, stream=_stream())
    assert recs[0]["outcome"] == "infra_void"
    assert recs[0]["infra_error"]
