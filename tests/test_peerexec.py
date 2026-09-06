"""peerexec 的確定性測試——不碰模型、不碰 runs/。

每一條都對應 `vacant/peerexec.py` 的一句主張。主張與測試一一對照，
「機制講得出來但測不出來」的東西不准留在 docstring 裡。

⚠ 沙箱：§1–§7 一行沙箱都不碰（探針是注入的替身）。§8（R449 §四-3 的套件量具閘）
  裡有四條**會跑本機沙箱**——量具的主張是「這套驗收擋不擋得住已知壞草稿」，
  用假 runner 測只會測到假 runner。零模型呼叫、零 API 這一條不變。
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault(
    "VACANT_EVALPLUS_PATH", ".vacant-private/evalplus/MbppPlus-v0.2.0.jsonl.gz"
)

from vacant.identity import Identity, PublicIdentity  # noqa: E402
from vacant.logbook import LogEntry, Logbook  # noqa: E402
from vacant.peerexec import (Attestation, Executor, GaugeRecord,  # noqa: E402
                             ProbeResult, SuiteGaugeError, challenge_rerun,
                             commit_suite, commit_suite_with_gauge, form_verdict,
                             gauged_suite_index, open_suite, roster_of,
                             run_suite_gauge, select_by_quorum, sha256_hex,
                             suite_gate, suite_hash, verify_attestation,
                             verify_executor_chain)
from vacant.suitegauge import broken_stub  # noqa: E402

TS = 1_700_000_000_000


def task(task_id="t1", code="assert f(1) == 2\nassert f(2) == 3\n"):
    return {"task_id": task_id, "entry_point": "f",
            "visible_check": {"type": "run_python", "code": code, "timeout": 8}}


def truth_probe(truth: dict[str, ProbeResult]):
    """確定性的『真沙箱』替身：草稿 sha → 結果。誠實執行器全部共用它。"""
    def probe(code, _task):
        return truth[sha256_hex(code)]
    return probe


def liar_probe(truth, bribe_sha):
    def probe(code, _task):
        if sha256_hex(code) == bribe_sha:
            return ProbeResult(True, None, 2, True, None)
        return truth[sha256_hex(code)]
    return probe


def saboteur_probe():
    def probe(_code, _task):
        return ProbeResult(False, 1, 2, True, None)
    return probe


GOOD, BAD = "def f(x):\n    return x + 1\n", "def f(x):\n    return 0\n"
TRUTH = {sha256_hex(GOOD): ProbeResult(True, None, 2, True, None),
         sha256_hex(BAD): ProbeResult(False, 1, 2, True, None)}


def mk(n, probe):
    return [Executor(f"x{i}", Identity.generate(), Logbook(), probe) for i in range(n)]


def rule_runner(fn):
    """量具用的確定性 runner 替身：`fn(code, check_code) -> 通過?`。

    簽章與 `vacant.suitegauge.CheckRunner`／`gain_run.meets_demand` 對齊。
    §8 真正要證明量具有牙齒的那幾條**不用**這個，用真沙箱。
    """
    def run(code, check_code, entry_point=None, timeout_s=10):
        return bool(fn(code, check_code)), ""
    return run


def verdict_for(execs, t, code, quorum=None):
    ros = roster_of(execs)
    ssha = suite_hash(t)
    atts = [e.attest(t, code, suite_sha256=ssha, ts_ms=TS) for e in execs]
    q = quorum if quorum is not None else len(execs) // 2 + 1
    return form_verdict(atts, ros, task_id=t["task_id"], draft_sha256=sha256_hex(code),
                        suite_sha256=ssha, quorum=q), atts, ros


# ── 1. 誠實的執行器永遠一致 ────────────────────────────────────────────────
@pytest.mark.parametrize("k", [1, 3, 5, 7])
@pytest.mark.parametrize("code", [GOOD, BAD])
def test_honest_executors_always_agree(k, code):
    """確定性驗收套件 ⇒ 誠實執行器必須全票一致、沒有少數方。這是全部主張的地基。"""
    t = task()
    v, _atts, _ros = verdict_for(mk(k, truth_probe(TRUTH)), t, code)
    assert v.n_admitted == k
    assert v.unanimous and not v.contested
    assert v.dissenters == () and v.detail_dissenters == () and v.equivocators == ()
    assert v.visible_ok is (code is GOOD)


def test_honest_chain_verifies_and_is_append_only():
    """證言釘在自己的鏈上：驗鏈過，且抽掉中間一筆就驗不過（不能事後否認）。"""
    t = task()
    execs = mk(1, truth_probe(TRUTH))
    e = execs[0]
    for c in (GOOD, BAD, GOOD):
        e.attest(t, c, ts_ms=TS)
    ros = roster_of(execs)
    assert verify_executor_chain("x0", e.book, ros)
    tampered = Logbook([e.book.entries[0], e.book.entries[2]])
    assert not verify_executor_chain("x0", tampered, ros)


# ── 2. 三個裡有一個說謊：被推翻，而且被指名 ────────────────────────────────
def test_single_liar_among_three_is_outvoted_and_named():
    t = task()
    honest = mk(2, truth_probe(TRUTH))
    liar = Executor("liar", Identity.generate(), Logbook(), liar_probe(TRUTH, sha256_hex(BAD)))
    execs = honest + [liar]
    v, atts, ros = verdict_for(execs, t, BAD)
    assert v.visible_ok is False                      # 被推翻
    assert v.dissenters == ("liar",)                  # 被指名
    assert v.n_pass == 1 and v.n_fail == 2
    assert not v.unanimous and v.contested
    # 指名不是標籤，是可獨立核對的證據：那一筆證言驗得過，且內容就是那句謊。
    ev = dict(v.evidence)
    lie = next(a for a in atts if a.executor_id == "liar")
    assert ev["liar"] == lie.entry_hash
    assert verify_attestation(lie, ros, task_id="t1", draft_sha256=sha256_hex(BAD),
                              suite_sha256=suite_hash(t)) == (True, "")
    assert lie.payload["visible_ok"] is True


def test_liar_cannot_move_the_verdict_alone_but_leaves_a_trail():
    """說謊者被推翻之後，那份草稿仍然不出貨——被指名不是安慰獎，是機制的產物。"""
    t = task()
    execs = mk(2, truth_probe(TRUTH)) + [
        Executor("liar", Identity.generate(), Logbook(), liar_probe(TRUTH, sha256_hex(BAD)))]
    sel = select_by_quorum(t, [(BAD, "wA"), (GOOD, "wB")], execs, ts_ms=TS)
    assert sel.shipped_index == 1 and sel.shipped_worker == "wB"
    assert sel.verdicts[0].dissenters == ("liar",)
    assert sel.verdicts[1].unanimous


# ── 3. 三個裡有兩個共謀：翻掉判決（多數決上界，寫死在這裡）────────────────
def test_two_colluders_among_three_flip_the_verdict_and_invert_attribution():
    """**這是機制的破口，不是 bug。**

    多數決容忍的上界是 ⌊(k-1)/2⌋。k=3 時上界是 1；兩個共謀者過半，於是：
      - 判決翻成他們要的那個（一份 hidden 錯的草稿被判通過）；
      - `dissenters` 反過來指名**誠實的那一位**。
    機制在這裡量到的東西仍然是真的——「有人不一致」——但**歸屬的方向錯了**，
    而機制自己分不出來。任何對外說法都必須帶這一句。
    """
    t = task()
    bribe = sha256_hex(BAD)
    colluders = [Executor(f"c{i}", Identity.generate(), Logbook(), liar_probe(TRUTH, bribe))
                 for i in range(2)]
    honest = Executor("h0", Identity.generate(), Logbook(), truth_probe(TRUTH))
    v, _atts, _ros = verdict_for(colluders + [honest], t, BAD)
    assert v.visible_ok is True                       # 翻掉了
    assert v.dissenters == ("h0",)                    # 歸屬反轉：誠實的被指名
    assert v.n_pass == 2 and v.n_fail == 1
    # 共謀者內部零分歧：除了自己的 id，兩人的判決欄位完全相同 ⇒ 沒有可歸屬的痕跡。
    assert v.camp_pass == ("c0", "c1")


def test_majority_bound_holds_at_the_edge():
    """k=5：兩個共謀者（≤⌊(5-1)/2⌋）擋得住，三個就擋不住。上界是算出來的，不是調出來的。"""
    t = task()
    bribe = sha256_hex(BAD)
    for n_bad, expect_ok in ((2, False), (3, True)):
        bad = [Executor(f"c{i}", Identity.generate(), Logbook(), liar_probe(TRUTH, bribe))
               for i in range(n_bad)]
        good = [Executor(f"h{i}", Identity.generate(), Logbook(), truth_probe(TRUTH))
                for i in range(5 - n_bad)]
        v, _a, _r = verdict_for(bad + good, t, BAD)
        assert v.visible_ok is expect_ok, n_bad


def test_tie_is_undecided_and_the_gate_refuses():
    """偶數人數會平手。平手不是通過的證據 ⇒ 未決 ⇒ 拒交。刻意的不對稱。"""
    t = task()
    execs = [Executor("c0", Identity.generate(), Logbook(), liar_probe(TRUTH, sha256_hex(BAD))),
             Executor("h0", Identity.generate(), Logbook(), truth_probe(TRUTH))]
    v, _a, _r = verdict_for(execs, t, BAD, quorum=2)
    assert v.visible_ok is None and v.contested and v.dissenters == ()
    sel = select_by_quorum(t, [(BAD, "wA")], execs, quorum=2, ts_ms=TS)
    assert sel.refused


# ── 4. 竄改證言就驗不過 ────────────────────────────────────────────────────
def test_tampering_an_attestation_breaks_verification():
    t = task()
    execs = mk(1, truth_probe(TRUTH))
    att = execs[0].attest(t, BAD, ts_ms=TS)
    ros = roster_of(execs)
    assert verify_attestation(att, ros)[0]
    # (a) 竄改判決本身
    bad_payload = dict(att.payload) | {"visible_ok": True}
    forged = Attestation("x0", LogEntry(att.entry.stream_id, att.entry.branch_id,
                                        att.entry.seq, att.entry.prev_hash,
                                        att.entry.ts_ms, att.entry.type,
                                        bad_payload, att.entry.sig))
    assert verify_attestation(forged, ros) == (False, "bad_signature")
    # (b) 竄改鏈上位置（把同一筆搬到別的 seq）
    moved = Attestation("x0", LogEntry(att.entry.stream_id, att.entry.branch_id,
                                       att.entry.seq + 7, att.entry.prev_hash,
                                       att.entry.ts_ms, att.entry.type,
                                       att.entry.payload, att.entry.sig))
    assert verify_attestation(moved, ros) == (False, "bad_signature")
    # (c) 換一把自己的金鑰重簽同一句話——名冊上的公鑰驗不過，冒名擋掉
    impostor = Executor("x0", Identity.generate(), Logbook(), truth_probe(TRUTH))
    fake = impostor.attest(t, BAD, ts_ms=TS)
    assert verify_attestation(fake, ros) == (False, "bad_signature")
    # (d) 名冊外的人投票
    outsider = Executor("nobody", Identity.generate(), Logbook(), truth_probe(TRUTH))
    assert verify_attestation(outsider.attest(t, BAD, ts_ms=TS), ros) == (
        False, "unknown_executor")


def test_forged_attestation_is_rejected_from_the_verdict_not_counted():
    """驗不過的證言不是「一張反對票」，是**根本不進計票**，而且理由要進收據。"""
    t = task()
    execs = mk(3, truth_probe(TRUTH))
    ros = roster_of(execs)
    ssha = suite_hash(t)
    atts = [e.attest(t, BAD, suite_sha256=ssha, ts_ms=TS) for e in execs]
    a0 = atts[0]
    atts[0] = Attestation("x0", LogEntry(a0.entry.stream_id, a0.entry.branch_id,
                                         a0.entry.seq, a0.entry.prev_hash, a0.entry.ts_ms,
                                         a0.entry.type, dict(a0.payload) | {"visible_ok": True},
                                         a0.entry.sig))
    v = form_verdict(atts, ros, task_id="t1", draft_sha256=sha256_hex(BAD),
                     suite_sha256=ssha, quorum=2)
    assert v.n_admitted == 2 and v.rejected == (("x0", "bad_signature"),)
    assert v.visible_ok is False and v.dissenters == ()
    # 驗不過的證言比「少數方」更硬 ⇒ 必須翻動警報，否則只看 unanimous 的人會漏掉它。
    assert v.contested and not v.unanimous


def test_equivocation_is_a_provable_fault_and_voids_both_votes():
    """同一個執行器對同一份草稿交出兩份不同的簽章證言 ⇒ 兩份都作廢、進 equivocators。

    這比「少數方」強一級：不需要跟任何人比對就已經是自證的過錯。
    """
    t = task()
    honest = mk(2, truth_probe(TRUTH))
    two_faced = Executor("d0", Identity.generate(), Logbook(), truth_probe(TRUTH))
    ros = roster_of(honest + [two_faced])
    ssha = suite_hash(t)
    atts = [e.attest(t, BAD, suite_sha256=ssha, ts_ms=TS) for e in honest]
    atts.append(two_faced.attest(t, BAD, suite_sha256=ssha, ts_ms=TS))
    two_faced.probe = liar_probe(TRUTH, sha256_hex(BAD))
    atts.append(two_faced.attest(t, BAD, suite_sha256=ssha, ts_ms=TS))
    v = form_verdict(atts, ros, task_id="t1", draft_sha256=sha256_hex(BAD),
                     suite_sha256=ssha, quorum=2)
    assert v.equivocators == ("d0",) and ("d0", "equivocation") in v.rejected
    assert v.n_admitted == 2 and v.visible_ok is False


# ── 5. 驗收套件雜湊不符 ⇒ 拒收 ────────────────────────────────────────────
def test_suite_hash_mismatch_is_rejected():
    """執行器跑的必須是**這一套**驗收。跑了別套（或跑了改過的那套）＝不進計票。"""
    t = task()
    swapped = {**t, "visible_check": task(code="assert f(1) == 999\n")["visible_check"]}
    assert suite_hash(t) != suite_hash(swapped)
    execs = mk(1, truth_probe(TRUTH))
    ros = roster_of(execs)
    # 同一題、同一份草稿，但執行器跑的是被換掉的驗收套件 ⇒ 不進計票。
    att = execs[0].attest(swapped, GOOD, ts_ms=TS)
    assert verify_attestation(att, ros, task_id="t1", draft_sha256=sha256_hex(GOOD),
                              suite_sha256=suite_hash(t)) == (False, "suite_mismatch")
    # 換題目的證言同樣擋掉（跨題重放）。
    att2 = execs[0].attest(task("t2"), GOOD, ts_ms=TS)
    assert verify_attestation(att2, ros, task_id="t1", draft_sha256=sha256_hex(GOOD),
                              suite_sha256=suite_hash(t)) == (False, "task_mismatch")


def test_replayed_attestation_from_another_draft_is_rejected():
    """把上一份草稿的『通過』證言貼到這一份 ⇒ draft_mismatch，擋掉重放。"""
    t = task()
    execs = mk(1, truth_probe(TRUTH))
    att = execs[0].attest(t, GOOD, ts_ms=TS)
    assert verify_attestation(att, roster_of(execs), task_id="t1",
                              draft_sha256=sha256_hex(BAD),
                              suite_sha256=suite_hash(t)) == (False, "draft_mismatch")


# ── 6. 剩下的固定點：套件的 commit-reveal 與重跑權 ─────────────────────────
def test_suite_commit_reveal_binds_the_suite_in_time():
    t = task()
    ident = Identity.generate()
    book = Logbook()
    nonce = "0123456789abcdef0123456789abcdef"
    # round749（R449 §四-3）：commit 現在要求一筆通過的量具紀錄。這一條測的仍然是
    # commit-reveal 的**時間綁定**，所以量具用注入的 runner 算（不碰沙箱）；
    # 量具本身的牙齒在 §8 測。
    gauge = run_suite_gauge(t["visible_check"]["code"], GOOD, [BAD],
                            entry_point="f", runner=rule_runner(lambda c, _k: c is GOOD))
    entry = commit_suite(book, ident, task_id="t1",
                         check_code=t["visible_check"]["code"], nonce=nonce,
                         gauge=gauge, ts_ms=TS)
    assert open_suite(entry, t["visible_check"]["code"], nonce)
    assert not open_suite(entry, t["visible_check"]["code"] + "\nassert f(9) == 10\n", nonce)
    assert not open_suite(entry, t["visible_check"]["code"], "f" * 32)
    assert book.verify_chain(
        __import__("vacant.identity", fromlist=["PublicIdentity"]).PublicIdentity(
            ident.vacant_id, ident.pub))


def test_challenge_rerun_overturns_a_saboteur_majority_with_a_clean_panel():
    """落敗方的重跑權：換一組乾淨的執行器再跑一次，同樣零模型呼叫。

    邊界（測試也要測邊界）：面板本身被腐化時重跑會**一致地覆述原判**，
    `outcome="upheld"` 不等於原判正確。
    """
    t = task()
    sab = [Executor(f"s{i}", Identity.generate(), Logbook(), saboteur_probe())
           for i in range(2)]
    execs = sab + [Executor("h0", Identity.generate(), Logbook(), truth_probe(TRUTH))]
    sel = select_by_quorum(t, [(GOOD, "wA")], execs, ts_ms=TS)
    assert sel.refused and sel.verdicts[0].dissenters == ("h0",)

    clean = mk(3, truth_probe(TRUTH))
    ch = challenge_rerun(t, GOOD, clean, sel.verdicts[0], ts_ms=TS)
    assert ch.outcome == "overturned" and ch.rerun.visible_ok is True
    assert "h0" in ch.accused          # 聯集：原判指名的人也要留在收據上

    dirty = [Executor(f"d{i}", Identity.generate(), Logbook(), saboteur_probe())
             for i in range(3)]
    assert challenge_rerun(t, GOOD, dirty, sel.verdicts[0], ts_ms=TS).outcome == "upheld"


# ── 7. 選擇語意與 CONFORM 逐字相同（k=1 時必須退化成 CONFORM）──────────────
def test_k1_reduces_to_conform():
    """k=1 的法定人數 ＝ 單一執行器 ＝ CONFORM。這是模擬校準檢查的機制側對應物。"""
    t = task()
    execs = mk(1, truth_probe(TRUTH))
    sel = select_by_quorum(t, [(BAD, "wA"), (BAD, "wB"), (GOOD, "wC")], execs, ts_ms=TS)
    assert sel.shipped_index == 2 and sel.n_sandbox_runs == 3
    assert not sel.refused
    sel2 = select_by_quorum(t, [(BAD, "wA"), (BAD, "wB")], execs, ts_ms=TS)
    assert sel2.refused and sel2.shipped_index is None
    # 拒交的收據仍然列出每一份卡在第幾條——R440P §六 那句話的實作。
    assert [v.as_receipt()["camp_fail"] for v in sel2.verdicts] == [["x0"], ["x0"]]


def test_a_corrupt_executor_that_agrees_with_the_majority_is_never_named():
    """**偵測率的分母紅線**：跟多數方一致的腐化執行器＝零痕跡，必須算成「沒偵測到」。

    這裡的 `sleeper` 買通的是**別的**草稿（GOOD），對本題這一份（BAD）照實跑，
    所以它在收據上與誠實執行器逐位相同。它仍然是腐化的——只是這一票沒有用到。
    `peer_exec_sim` 的 detect_* 分母因此是**全部腐化執行器**，不是「有說謊的那些」。
    """
    t = task()
    sleeper = Executor("sleeper", Identity.generate(), Logbook(),
                       liar_probe(TRUTH, sha256_hex(GOOD)))   # 目標不是這一份
    v, _a, _r = verdict_for(mk(2, truth_probe(TRUTH)) + [sleeper], t, BAD)
    assert v.unanimous and not v.contested
    assert v.dissenters == () and v.detail_dissenters == () and v.equivocators == ()
    assert "sleeper" in v.camp_fail          # 它有投票，而且投得跟誠實的人一樣
    assert v.visible_ok is False


def test_a_trivial_suite_ships_a_wrong_draft_with_zero_dissent():
    """**剩下的固定點，寫成測試**：驗收套件退化成「什麼都不驗」時，去中心化執行零幫助。

    執行器一個都沒有腐化、每條鏈都驗得過、`contested` 是 False、`dissenters` 是空的
    ——所有健康指標滿分——而出貨的是一份對真需求錯的草稿。`unanimous` 描述的是
    **觀察到的分佈**，不是真相；收據上不准把它讀成「這份草稿是對的」。
    """
    trivial = {"task_id": "t1", "entry_point": "f",
               "visible_check": {"type": "run_python", "code": "pass", "timeout": 8}}
    allpass = {sha256_hex(GOOD): ProbeResult(True, None, 0, True, None),
               sha256_hex(BAD): ProbeResult(True, None, 0, True, None)}
    execs = mk(5, truth_probe(allpass))
    sel = select_by_quorum(trivial, [(BAD, "wA"), (GOOD, "wB")], execs, ts_ms=TS)
    assert sel.shipped_index == 0 and sel.shipped_worker == "wA"   # 交了錯的那一份
    v = sel.verdicts[0]
    assert v.unanimous and not v.contested and v.n_pass == 5 and v.dissenters == ()
    # 而且這件事在收據上看得出來——換了套件，suite_sha256 就換了。
    assert v.suite_sha256 == suite_hash(trivial) != suite_hash(task())


def test_detail_dissent_names_a_saboteur_that_did_not_actually_run():
    """第二條歸屬通道：兩邊都說 FAIL，但『卡在第幾條』不同 ⇒ 有人沒真的跑。

    邊界：一個真的跑、只在布林值上說謊的破壞者不會被這條通道抓到（布林通道會）。
    """
    t = task()
    honest = mk(2, truth_probe(TRUTH))          # 真相：BAD 卡在第 1 條
    truth2 = dict(TRUTH) | {sha256_hex(BAD): ProbeResult(False, 2, 2, True, None)}
    honest = [Executor(f"h{i}", Identity.generate(), Logbook(), truth_probe(truth2))
              for i in range(2)]
    lazy = Executor("lazy", Identity.generate(), Logbook(), saboteur_probe())  # 永遠填 1
    v, _a, _r = verdict_for(honest + [lazy], t, BAD)
    assert v.visible_ok is False and v.dissenters == ()      # 布林票上完全一致
    assert v.detail_dissenters == ("lazy",)                  # 但條號出賣了他
    assert v.contested


# ── 8. 套件量具閘：套件要上鏈，先證明它擋得住已知壞草稿（R449 §四-3）─────────
NONCE = "0123456789abcdef0123456789abcdef"

#: 真 MBPP+ 題目（similar_elements）的參考解與一份壞解——**驗證者側**的物件：
#: 不是任何 worker 的產出、不進任何 prompt、不進 hidden_check 路徑（V/GT 分離）。
REF_SIMILAR = "def similar_elements(a, b):\n    return tuple(sorted(set(a) & set(b)))\n"
STUB_EMPTY = "def similar_elements(*a, **k):\n    return ()\n"


@pytest.fixture(scope="module")
def mbpp_task():
    """真 MBPP+ 的 similar_elements（官方包不在場就 skip，不假裝驗過）。"""
    from vacant.codebench import EvalPlusMBPPLoader
    try:
        tasks = EvalPlusMBPPLoader(expose_contract=True).iter_tasks("x")
    except FileNotFoundError:
        pytest.skip("EvalPlus 官方包不在本機（VM 上才有），跳過")
    for t in tasks:
        if t["entry_point"] == "similar_elements":
            return t
    pytest.skip("找不到基準題")


def test_trivial_suite_is_refused_at_commit(mbpp_task):
    """**這一條就是 R449 §三-3 的封口**：`visible_check := "pass"` 上不了鏈。

    真沙箱。壞樁（`return None`）在「什麼都不驗」的套件下**通過** ⇒ 壞解被擋 0/1
    ⇒ 量具不合格 ⇒ `SuiteGaugeError`，而且**鏈上一筆都沒有**（不是記一筆失敗）。
    模擬側的同一件事：`peer_exec_sim --trivial-suite` 那 8 格的交付全部收不到閘後面。
    """
    book, ident = Logbook(), Identity.generate()
    with pytest.raises(SuiteGaugeError) as e:
        commit_suite_with_gauge(book, ident, task_id="t1", check_code="pass",
                                nonce=NONCE, reference=REF_SIMILAR,
                                entry_point="similar_elements", ts_ms=TS)
    assert "gauge_failed" in str(e.value) and "all_rejected=False" in str(e.value)
    assert book.entries == []


def test_real_mbpp_suite_is_accepted_at_commit(mbpp_task):
    """反方向的對照：真的 MBPP+ 可見驗收套件**過得了**閘（不然這道閘只是把門焊死）。"""
    book, ident = Logbook(), Identity.generate()
    code = mbpp_task["visible_check"]["code"]
    entry = commit_suite_with_gauge(
        book, ident, task_id=mbpp_task["task_id"], check_code=code, nonce=NONCE,
        reference=REF_SIMILAR, entry_point="similar_elements", ts_ms=TS)
    rec = GaugeRecord.from_payload(entry.payload["gauge"])
    assert rec.ref_passed and rec.all_rejected and rec.n_broken == 1 and rec.ok
    assert rec.suite_sha256 == suite_hash(mbpp_task) == sha256_hex(code)
    assert rec.ref_sha256 == sha256_hex(REF_SIMILAR)
    assert open_suite(entry, code, NONCE)
    assert suite_gate(entry, code, NONCE,
                      who=PublicIdentity(ident.vacant_id, ident.pub)) == (True, "")
    assert book.verify_chain(PublicIdentity(ident.vacant_id, ident.pub))


def test_suite_that_passes_the_reference_but_admits_one_broken_stub_is_refused():
    """通過參考解**不夠**：只要一個已知壞樁溜過去，套件就上不了鏈。

    真沙箱。這套驗收只檢查「回傳的不是 None」——參考解過、`return None` 樁被擋，
    但 `return ()` 樁大搖大擺走過去。單向的量具會給它綠燈，雙向＋多樁的不會。
    """
    weak = "assert similar_elements([3, 4, 5], [4, 5, 6]) is not None\n"
    book, ident = Logbook(), Identity.generate()
    ok_one = run_suite_gauge(weak, REF_SIMILAR, [broken_stub("similar_elements")],
                             entry_point="similar_elements")
    assert ok_one.ok            # 只放一個樁 ⇒ 這套爛驗收會被放行（量具是下界）
    with pytest.raises(SuiteGaugeError) as e:
        commit_suite_with_gauge(
            book, ident, task_id="t1", check_code=weak, nonce=NONCE,
            reference=REF_SIMILAR,
            broken_stubs=[broken_stub("similar_elements"), STUB_EMPTY],
            entry_point="similar_elements", ts_ms=TS)
    assert "gauge_failed" in str(e.value) and "ref_passed=True" in str(e.value)
    assert book.entries == []


def test_an_empty_known_bad_set_is_not_a_pass():
    """零個壞樁 ⇒ 「全部被擋」空洞地成立。fail-open 要在 commit 就被擋下來。"""
    rec = run_suite_gauge("pass", GOOD, [], runner=rule_runner(lambda *_: True))
    assert rec.ref_passed and rec.n_broken == 0 and not rec.ok
    with pytest.raises(SuiteGaugeError) as e:
        commit_suite(Logbook(), Identity.generate(), task_id="t1", check_code="pass",
                     nonce=NONCE, gauge=rec, ts_ms=TS)
    assert "n_broken=0" in str(e.value)


def _gauged_commit(check_code, *, task_id="t1"):
    """把一套（假設已驗過的）驗收合法地上鏈，回傳 (entry, book, identity)。"""
    book, ident = Logbook(), Identity.generate()
    rec = run_suite_gauge(check_code, GOOD, [BAD], entry_point="f",
                          runner=rule_runner(lambda c, _k: c is GOOD))
    return commit_suite(book, ident, task_id=task_id, check_code=check_code,
                        nonce=NONCE, gauge=rec, ts_ms=TS), book, ident


def test_tampering_the_gauge_record_breaks_chain_verification():
    """把 `all_rejected` 從 True 改成 False（或反過來）＝改 payload ＝簽章壞掉。

    量具紀錄不是旁邊的一張紙條，它**在簽章覆蓋的範圍內**：改它就得重簽整條鏈。
    兩個方向都測——調高（假造合格）與調低（事後賴帳）都要驗不過。
    """
    t = task()
    code = t["visible_check"]["code"]
    entry, book, ident = _gauged_commit(code)
    who = PublicIdentity(ident.vacant_id, ident.pub)
    assert book.verify_chain(who) and open_suite(entry, code, NONCE)

    def mutate(**over):
        p = dict(entry.payload)
        p["gauge"] = dict(p["gauge"]) | over
        return LogEntry(entry.stream_id, entry.branch_id, entry.seq, entry.prev_hash,
                        entry.ts_ms, entry.type, p, entry.sig)

    # (a) 事後賴帳：把 all_rejected 改成 False。鏈驗不過，而且內容本身就已經不合格。
    lowered = mutate(all_rejected=False)
    assert not Logbook([lowered]).verify_chain(who)
    assert suite_gate(lowered, code, NONCE) == (False, "gauge_failed")
    # (b) 假造更強的合格證：把 n_broken 從 1 灌水成 99。內容檢查**抓不到**這個
    #     （灌水後的紀錄照樣「合格」）——只有簽章抓得到。這條邊界要寫出來：
    #     量具紀錄的可信度來自簽章鏈，不是來自它自己說了什麼。
    inflated = mutate(n_broken=99)
    assert not Logbook([inflated]).verify_chain(who)
    assert suite_gate(inflated, code, NONCE) == (True, "")            # 內容看不出來
    assert suite_gate(inflated, code, NONCE, who=who) == (False, "bad_signature")


def test_open_suite_refuses_a_commit_without_a_gauge_record():
    """沒有量具紀錄的承諾**不是**一套可用的驗收——缺席就是拒，不是「沒查到」。"""
    t = task()
    code = t["visible_check"]["code"]
    entry, _book, ident = _gauged_commit(code)
    bare = LogEntry(entry.stream_id, entry.branch_id, entry.seq, entry.prev_hash,
                    entry.ts_ms, entry.type,
                    {k: v for k, v in entry.payload.items() if k != "gauge"}, entry.sig)
    assert suite_gate(bare, code, NONCE) == (False, "gauge_record_missing")
    assert not open_suite(bare, code, NONCE)
    # 綁錯套件的紀錄也擋掉（拿別題的合格證來用）。
    other = dict(entry.payload)
    other["gauge"] = dict(other["gauge"]) | {"suite_sha256": sha256_hex("pass")}
    assert suite_gate(LogEntry(entry.stream_id, entry.branch_id, entry.seq,
                               entry.prev_hash, entry.ts_ms, entry.type, other,
                               entry.sig), code, NONCE) == (False, "gauge_suite_mismatch")


def test_form_verdict_rejects_attestations_against_an_uncommitted_suite():
    """套件沒上鏈（不在白名單）⇒ 每一票都不進計票、判決未決 ⇒ 拒交。"""
    t = task()
    execs = mk(3, truth_probe(TRUTH))
    ros = roster_of(execs)
    ssha = suite_hash(t)
    atts = [e.attest(t, GOOD, suite_sha256=ssha, ts_ms=TS) for e in execs]
    v = form_verdict(atts, ros, task_id="t1", draft_sha256=sha256_hex(GOOD),
                     suite_sha256=ssha, quorum=2, gauged_suites={})
    assert v.gauge_status == "suite_not_gauged"
    assert v.visible_ok is None and v.n_admitted == 0 and v.contested
    assert sorted(v.rejected) == [("x0", "suite_not_gauged"), ("x1", "suite_not_gauged"),
                                  ("x2", "suite_not_gauged")]
    assert v.as_receipt()["gauge_status"] == "suite_not_gauged"


def test_form_verdict_rejects_a_suite_whose_gauge_record_failed():
    """白名單裡有這套、但紀錄是不合格的 ⇒ 同樣一票都不採信（理由分開報）。"""
    t = task()
    execs = mk(3, truth_probe(TRUTH))
    ssha = suite_hash(t)
    atts = [e.attest(t, GOOD, suite_sha256=ssha, ts_ms=TS) for e in execs]
    failed = GaugeRecord(ssha, sha256_hex(GOOD), 1, False, True)   # 壞樁溜過去了
    v = form_verdict(atts, roster_of(execs), task_id="t1",
                     draft_sha256=sha256_hex(GOOD), suite_sha256=ssha, quorum=2,
                     gauged_suites={ssha: failed})
    assert v.gauge_status == "suite_gauge_failed" and v.visible_ok is None
    assert v.n_admitted == 0 and v.contested
    # 合格的紀錄則放行，判決回到原本的語意。
    good = GaugeRecord(ssha, sha256_hex(GOOD), 1, True, True)
    v2 = form_verdict(atts, roster_of(execs), task_id="t1",
                      draft_sha256=sha256_hex(GOOD), suite_sha256=ssha, quorum=2,
                      gauged_suites={ssha: good})
    assert v2.gauge_status == "ok" and v2.visible_ok is True and v2.unanimous


def test_gauged_suite_index_only_admits_gate_passing_commits():
    """白名單的建構函式自己 fail-closed：揭露對不上的承諾進不了索引。"""
    t = task()
    code = t["visible_check"]["code"]
    entry, _b, _i = _gauged_commit(code)
    idx = gauged_suite_index([(entry, code, NONCE)])
    assert set(idx) == {suite_hash(t)} and idx[suite_hash(t)].ok
    assert gauged_suite_index([(entry, code, "f" * 32)]) == {}          # nonce 不對
    assert gauged_suite_index([(entry, code + "\n", NONCE)]) == {}      # 套件不對


def test_a_trivial_suite_no_longer_ships_once_the_gate_is_on():
    """把 §7 那一條（爛套件零爭議地交垃圾）接到閘門後面：現在交不出去。

    同一組誠實執行器、同一份「什麼都放行」的探針。差別只有一個：這一套驗收
    沒有合格的量具紀錄。⇒ 拒交、`refusal_reason` 指名是**套件**不是候選、
    而且 `n_sandbox_runs=0`——連跑都不跑（量具紀錄必須在證言之前）。
    """
    trivial = {"task_id": "t1", "entry_point": "f",
               "visible_check": {"type": "run_python", "code": "pass", "timeout": 8}}
    allpass = {sha256_hex(GOOD): ProbeResult(True, None, 0, True, None),
               sha256_hex(BAD): ProbeResult(True, None, 0, True, None)}
    execs = mk(5, truth_probe(allpass))
    # 閘門關著（舊語意）：照樣交出錯的那一份，所有健康指標滿格——R449 §三-3。
    before = select_by_quorum(trivial, [(BAD, "wA"), (GOOD, "wB")], execs, ts_ms=TS)
    assert before.shipped_index == 0 and before.verdicts[0].unanimous
    assert before.verdicts[0].gauge_status == "unchecked"
    # 閘門開著：這套驗收根本沒有合格紀錄 ⇒ 拒交。
    after = select_by_quorum(trivial, [(BAD, "wA"), (GOOD, "wB")], execs, ts_ms=TS,
                             gauged_suites={})
    assert after.refused and after.shipped_index is None
    assert after.refusal_reason == "suite_gate:suite_not_gauged"
    assert after.verdicts[0].gauge_status == "suite_not_gauged"
    assert after.as_receipt()["refusal_reason"] == "suite_gate:suite_not_gauged"


def test_select_by_quorum_refuses_before_spending_a_single_sandbox_run():
    """`suite_commit` 有給的時候，閘在**第一次沙箱之前**。爛套件不該先燒 k 次執行。"""
    t = task()
    code = t["visible_check"]["code"]
    entry, _b, _i = _gauged_commit(code)
    execs = mk(3, truth_probe(TRUTH))
    # (a) 承諾的是別套驗收 ⇒ 連一次沙箱都不跑
    swapped = {**t, "visible_check": {"type": "run_python", "code": "pass", "timeout": 8}}
    sel = select_by_quorum(swapped, [(GOOD, "wA")], execs, suite_commit=entry,
                           suite_nonce=NONCE, ts_ms=TS)
    assert sel.refused and sel.n_sandbox_runs == 0 and sel.verdicts == ()
    assert sel.refusal_reason == "suite_gate:commitment_mismatch"
    # (b) 對得上的套件則照常出貨，語意與沒有閘門時逐字相同
    sel2 = select_by_quorum(t, [(BAD, "wA"), (GOOD, "wB")], execs, suite_commit=entry,
                            suite_nonce=NONCE, ts_ms=TS)
    assert sel2.shipped_index == 1 and sel2.n_sandbox_runs == 6
    assert all(v.gauge_status == "ok" for v in sel2.verdicts)
    assert sel2.refusal_reason is None


def test_default_broken_stub_matches_probe_instrument():
    """反漂移：`suitegauge.broken_stub` 必須與 `gain_run.probe_instrument` 的樁逐字相同。

    用 `ops/gain/r474_stub_sweep.py` 那支 AST 抽取器逐字取回來再 eval——兩份實作
    只要有一天分家，這條就會吵，而不是安靜地用兩個不同的樁量兩件事。
    """
    from ops.gain.r474_stub_sweep import stub_expr_source
    src = stub_expr_source()
    for ep in ("f", "similar_elements", None):
        expected = eval(src, {"t": {"entry_point": ep} if ep else {}})  # noqa: S307
        assert broken_stub(ep) == expected


# ── 9. 量具的誠實上限：通過量具、但照樣交垃圾的套件（R449 §七 推翻條件二）─────
def test_a_suite_can_read_the_candidate_source_from_the_runner():
    """實測（不是假設）：驗收碼看得見候選的**原始碼**，不只是它的行為。

    `vacant/checks.py::_test_runner_source` 把套件原文**內嵌**進 runner 行程，而
    `_worker`（跑候選的那個 `subprocess.Popen`）就在同一個命名空間裡，
    `_worker.args` 帶著 `candidate.py` 的路徑。AST 白名單只掃**候選**，不掃套件。

    ⇒ 內容定址的白／黑名單套件在這顆沙箱上是**可行的**，不是理論上的。
      V/GT 分離沒有被破（讀到的是候選自己的產出，不是 hidden_check、不是參考解），
      但這條管道要記進誠實邊界——`peer_exec_sim.targeted_suite` 就是靠它。
    """
    from ops.gain.gain_run import meets_demand
    marker = "vacant_r449_marker_" + "8f21c0"
    peek = (
        "_p = next(p for p in _worker.args if str(p).endswith('candidate.py'))\n"
        "with open(_p, encoding='utf-8') as _fh:\n"
        "    _src = _fh.read()\n"
        f"assert {marker!r} in _src\n"
    )
    with_marker = f"def f(x):\n    return x + 1  # {marker}\n"
    without = "def f(x):\n    return x + 1\n"
    assert meets_demand(with_marker, peek, 10, entry_point="f")[0] is True
    # 同一份行為、只差一行註解 ⇒ 判決翻轉。這證明它讀的是原始碼不是行為。
    assert meets_demand(without, peek, 10, entry_point="f")[0] is False


def test_a_targeted_suite_passes_the_gauge_and_still_ships_anything(mbpp_task):
    """**這道閘的誠實上限**：逐字黑名單那組已知壞樁的套件，量具滿分、上得了鏈。

    真沙箱、真簽章、真鏈。這一套驗收一次都沒有呼叫過候選函式，它只把候選原始碼的
    sha256 拿去比對那組壞樁的字面：命中就失敗，沒命中就 rc=0。於是

      - 量具兩個方向**滿分**（參考解通過、四個壞樁全被擋）⇒ `commit_suite` 收下它；
      - 任何一份真候選——包括回傳 `'lol'` 的——都通過 ⇒ k 台誠實執行器一致地
        交出垃圾，`contested=False`，收據上一個警告都不會亮。

    數字版本見 `peer_exec_sim --gauge-gate` 的 `targeted` 那一列。
    """
    from ops.gain.replay.peer_exec_sim import stub_set, targeted_suite
    ep = mbpp_task["entry_point"]
    suite = targeted_suite(ep)
    rec = run_suite_gauge(suite, REF_SIMILAR, stub_set(ep), entry_point=ep)
    assert rec.ok and rec.ref_passed and rec.all_rejected and rec.n_broken == 4

    book, ident = Logbook(), Identity.generate()
    entry = commit_suite_with_gauge(
        book, ident, task_id=mbpp_task["task_id"], check_code=suite, nonce=NONCE,
        reference=REF_SIMILAR, broken_stubs=stub_set(ep), entry_point=ep, ts_ms=TS)
    assert suite_gate(entry, suite, NONCE) == (True, "")     # 閘門放行

    junk = f"def {ep}(a, b):\n    return 'lol'\n"
    t = {**mbpp_task,
         "visible_check": {"type": "run_python", "code": suite, "timeout": 10}}
    execs = [Executor(f"x{i}", Identity.generate(), Logbook()) for i in range(3)]
    sel = select_by_quorum(t, [(junk, "wA")], execs, quorum=2, suite_commit=entry,
                           suite_nonce=NONCE, ts_ms=TS)
    assert sel.shipped_index == 0 and not sel.refused        # 垃圾出貨
    assert sel.verdicts[0].unanimous and not sel.verdicts[0].contested
    assert sel.verdicts[0].gauge_status == "ok"              # 收據說「量具通過」
    # 同一份垃圾在**真的** MBPP+ 可見驗收下是擋得住的——差別只在套件。
    real = {**mbpp_task}
    assert select_by_quorum(real, [(junk, "wA")], execs, quorum=2, ts_ms=TS).refused


def test_a_behavioural_stub_blacklist_also_passes_the_gauge():
    """堵掉讀檔管道也沒有用：**純行為**版的黑名單一樣量具滿分、一樣放行垃圾。

    這一套只呼叫候選一次，然後斷言回傳值不是那四個已知壞樁會回的東西
    （`None`／`0`／`[]`／第一個參數）。不讀檔、不看原始碼、不用 `_worker`——
    所以「把 `vacant/checks.py` 的讀檔管道封起來」不是解法。

    解法只有一句話，而且它必須一直掛在收據上：**量具是下界，不是保證**
    （`SUITE_FIXED_POINT_NOTE`）。
    """
    from ops.gain.gain_run import meets_demand
    ep = "similar_elements"
    blacklist = (
        "_r = similar_elements([3, 4, 5], [4, 5, 6])\n"
        "assert _r is not None\n"
        "assert _r != 0\n"
        "assert _r != []\n"
        "assert _r != [3, 4, 5]\n"
    )
    stubs = [broken_stub(ep),
             f"def {ep}(*a, **k):\n    return 0\n",
             f"def {ep}(*a, **k):\n    return []\n",
             f"def {ep}(*a, **k):\n    return a[0] if a else None\n"]
    rec = run_suite_gauge(blacklist, REF_SIMILAR, stubs, entry_point=ep)
    assert rec.ok and rec.n_broken == 4 and rec.all_rejected   # 量具滿分
    junk = f"def {ep}(a, b):\n    return 'lol'\n"
    assert meets_demand(junk, blacklist, 10, entry_point=ep)[0] is True
    # 對照：真的 MBPP+ 可見驗收擋得住同一份垃圾（見上一條）。
    entry = commit_suite_with_gauge(
        Logbook(), Identity.generate(), task_id="t1", check_code=blacklist,
        nonce=NONCE, reference=REF_SIMILAR, broken_stubs=stubs, entry_point=ep,
        ts_ms=TS)
    assert suite_gate(entry, blacklist, NONCE) == (True, "")


def test_select_by_quorum_verifies_the_committers_signature_when_given_the_key():
    """灌水的量具紀錄：內容看不出來，**簽章看得出來**——出貨路徑要帶公鑰。

    `n_broken` 從 1 改成 99 之後這筆紀錄在內容上更「合格」，`suite_gate` 不帶 `who`
    照樣放行（上一條已經證明）。這裡把承諾者的公鑰帶進 `select_by_quorum`：
    同一份灌水承諾變成 `suite_gate:bad_signature`，而且**一次沙箱都不花**。
    """
    t = task()
    code = t["visible_check"]["code"]
    entry, _b, ident = _gauged_commit(code)
    who = PublicIdentity(ident.vacant_id, ident.pub)
    execs = mk(3, truth_probe(TRUTH))
    # 帶公鑰、承諾沒被動過 ⇒ 照常出貨
    ok = select_by_quorum(t, [(BAD, "wA"), (GOOD, "wB")], execs, suite_commit=entry,
                          suite_nonce=NONCE, suite_committer=who, ts_ms=TS)
    assert ok.shipped_index == 1 and ok.refusal_reason is None
    # 灌水之後
    p = dict(entry.payload)
    p["gauge"] = dict(p["gauge"]) | {"n_broken": 99}
    forged = LogEntry(entry.stream_id, entry.branch_id, entry.seq, entry.prev_hash,
                      entry.ts_ms, entry.type, p, entry.sig)
    blind = select_by_quorum(t, [(GOOD, "wB")], execs, suite_commit=forged,
                             suite_nonce=NONCE, ts_ms=TS)
    assert not blind.refused                                   # 不帶公鑰＝看不見
    caught = select_by_quorum(t, [(GOOD, "wB")], execs, suite_commit=forged,
                              suite_nonce=NONCE, suite_committer=who, ts_ms=TS)
    assert caught.refused and caught.n_sandbox_runs == 0
    assert caught.refusal_reason == "suite_gate:bad_signature"


def test_a_mimic_suite_defeats_even_a_detail_matching_gauge(mbpp_task):
    """量具的**最強**攻擊：與真套件逐位相同，只多一句「不是已知壞樁就換掉受測函式」。

    比 `targeted_suite` 難擋一個層次。targeted 自己捏一句 assert 去擋壞樁，所以它的
    **形狀**（`_visible_test_slicer` 認不認得）與**失敗細節**（`first_failing_test`／
    `n_visible_tests`）都跟真套件不一樣——一個被強化成「連失敗的樣子都要對」的量具
    抓得到它。mimic 不會：

      - 量具兩個方向滿分（參考解通過、四個已知壞樁全被擋）⇒ `commit_suite` 收下；
      - 已知壞樁走的是**原封不動的真套件** ⇒ `conform_failure_detail` 的三個欄位
        與真套件**逐欄相同**（本條逐樁比對）；
      - 其餘任何候選——包括回傳 `'lol'` 的——受測函式已被換成該題自帶的參考解
        ⇒ 一律通過，k 台誠實執行器一致地交垃圾，收據上一個警告都不會亮。

    ⇒ 把量具從「壞樁被擋?」強化到「壞樁被擋的樣子對不對?」也救不回來。這是
      R449 §七推翻條件二的最強版本，也是 `SUITE_FIXED_POINT_NOTE` 的理由。
    """
    from ops.gain.gain_run import conform_failure_detail, meets_demand
    from ops.gain.replay.peer_exec_sim import mimic_suite, stub_set

    ep = mbpp_task["entry_point"]
    stubs = stub_set(ep)
    mimic = mimic_suite(mbpp_task["visible_check"]["code"], ep)
    assert mimic is not None

    rec = run_suite_gauge(mimic, REF_SIMILAR, stubs, entry_point=ep)
    assert rec.ok and rec.n_broken == len(stubs) and rec.all_rejected  # 量具滿分
    book, ident = Logbook(), Identity.generate()
    entry = commit_suite_with_gauge(
        book, ident, task_id=mbpp_task["task_id"], check_code=mimic, nonce=NONCE,
        reference=REF_SIMILAR, broken_stubs=stubs, entry_point=ep, ts_ms=TS)
    assert suite_gate(entry, mimic, NONCE,
                      who=PublicIdentity(ident.vacant_id, ident.pub)) == (True, "")

    # 強化版量具（比對失敗細節）也抓不到：壞樁在 mimic 下的細節＝真套件下的細節。
    mimic_task = {**mbpp_task,
                  "visible_check": {"type": "run_python", "code": mimic, "timeout": 10}}
    for stub in stubs:
        d_mimic = conform_failure_detail(stub, mimic_task)
        assert d_mimic == conform_failure_detail(stub, mbpp_task)
        assert d_mimic["detail_reason"] is None          # 形狀認得出來，不是 null 一片

    junk = f"def {ep}(a, b):\n    return 'lol'\n"
    assert meets_demand(junk, mimic, 10, entry_point=ep)[0] is True
    execs = [Executor(f"x{i}", Identity.generate(), Logbook()) for i in range(3)]
    sel = select_by_quorum(mimic_task, [(junk, "wA")], execs, quorum=2,
                           suite_commit=entry, suite_nonce=NONCE, ts_ms=TS)
    assert sel.shipped_index == 0 and not sel.refused
    assert sel.verdicts[0].gauge_status == "ok" and not sel.verdicts[0].contested
    # 對照：真套件擋得住同一份垃圾——差別只在套件。
    assert select_by_quorum(mbpp_task, [(junk, "wA")], execs, quorum=2,
                            ts_ms=TS).refused
