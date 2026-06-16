"""G2 驗收：簽得出、驗得過、改一筆被抓。crypto / logbook / envelope / reputation。"""

from __future__ import annotations

import pytest

from vacant import crypto
from vacant.body import now_ms
from vacant.envelope import ChannelGuard, Envelope, ReplayError
from vacant.identity import Identity, PublicIdentity
from vacant.logbook import Logbook
from vacant.reputation import Reputation, ucb_score


# --- crypto / vacant_id ------------------------------------------------------
def test_vacant_id_deterministic_and_multibase():
    idn = Identity.generate()
    again = crypto.vacant_id_from_pubkey(idn.pub)
    assert idn.vacant_id == again
    assert idn.vacant_id.startswith("z")  # multibase base58btc


def test_sign_verify_and_tamper():
    idn = Identity.generate()
    pub = PublicIdentity(idn.vacant_id, idn.pub)
    msg = b"vacant responsibility layer"
    sig = idn.sign(msg)
    assert pub.verify(msg, sig)
    assert not pub.verify(b"tampered", sig)


# --- logbook hash chain ------------------------------------------------------
def test_logbook_seq_monotonic_not_stuck_at_one():
    """修掉舊 repo「seq 永遠=1」的 bug：seq 必須 1,2,3,…"""
    idn = Identity.generate()
    lb = Logbook()
    for i in range(5):
        lb.append("INFERENCE", {"i": i}, idn, ts_ms=now_ms() + i)
    assert [e.seq for e in lb.entries] == [1, 2, 3, 4, 5]
    assert lb.verify_chain(PublicIdentity(idn.vacant_id, idn.pub))


def test_logbook_tamper_detected():
    idn = Identity.generate()
    who = PublicIdentity(idn.vacant_id, idn.pub)
    lb = Logbook()
    for i in range(4):
        lb.append("INFERENCE", {"i": i}, idn, ts_ms=now_ms() + i)
    assert lb.verify_chain(who)
    # 竄改中間一筆的 payload → 鏈驗不過
    lb.entries[1].payload = {"i": 999}
    assert not lb.verify_chain(who)


def test_logbook_wrong_signer_detected():
    a, b = Identity.generate(), Identity.generate()
    lb = Logbook()
    lb.append("INFERENCE", {"x": 1}, a, ts_ms=now_ms())
    assert lb.verify_chain(PublicIdentity(a.vacant_id, a.pub))
    assert not lb.verify_chain(PublicIdentity(b.vacant_id, b.pub))


def test_logbook_roundtrip(tmp_path):
    idn = Identity.generate()
    lb = Logbook()
    for i in range(3):
        lb.append("WAKE", {"i": i}, idn, ts_ms=now_ms() + i)
    p = tmp_path / "logbook.ndjson"
    lb.save(p)
    lb2 = Logbook.load(p)
    assert [e.seq for e in lb2.entries] == [1, 2, 3]
    assert lb2.verify_chain(PublicIdentity(idn.vacant_id, idn.pub))


# --- envelope: 冒名 / replay / 亂序 ------------------------------------------
def _env(sender: Identity, to: str, seq: int, prev: str, body) -> Envelope:
    return Envelope.create(sender, to=to, seq=seq, prev_hash=prev, ts_ms=now_ms(), kind="call", body=body)


def test_envelope_impersonation_rejected():
    alice, mallory = Identity.generate(), Identity.generate()
    # mallory 簽，卻宣稱來自 alice → 用 alice 公鑰驗 → 失敗
    env = _env(mallory, to="bob", seq=1, prev="0" * 64, body={"x": 1})
    env.frm = alice.vacant_id  # 偽造寄件者欄位
    assert not env.verify_sig(PublicIdentity(alice.vacant_id, alice.pub))


def test_envelope_replay_and_reorder_rejected():
    alice = Identity.generate()
    guard = ChannelGuard()
    e1 = _env(alice, "bob", 1, "0" * 64, {"n": 1})
    guard.accept(e1)
    e2 = _env(alice, "bob", 2, e1.hash(), {"n": 2})
    guard.accept(e2)
    # 重放 e1（seq 未前進）
    with pytest.raises(ReplayError):
        guard.accept(e1)
    # 亂序：prev_hash 不接
    bad = _env(alice, "bob", 3, "0" * 64, {"n": 3})
    with pytest.raises(ReplayError):
        guard.accept(bad)


def test_channel_guard_send_side_chains():
    alice = Identity.generate()
    g = ChannelGuard()
    seq1, prev1 = g.next_seq("bob")
    assert (seq1, prev1) == (1, "0" * 64)
    e1 = _env(alice, "bob", seq1, prev1, {"n": 1})
    g.record_sent(e1)
    seq2, prev2 = g.next_seq("bob")
    assert seq2 == 2 and prev2 == e1.hash()


# --- reputation --------------------------------------------------------------
def test_reputation_good_beats_bad():
    rep = Reputation()
    for _ in range(10):
        rep.record_review("good", "echo", {d: 1.0 for d in ("factual", "logical", "relevance", "honesty", "adoption")})
        rep.record_review("bad", "echo", {d: 0.0 for d in ("factual", "logical", "relevance", "honesty", "adoption")})
    assert rep.score("good", "echo") > 0.8
    assert rep.score("bad", "echo") < 0.2


def test_same_signal_discount_raises_cost():
    plain, sybil = Reputation(), Reputation()
    good = {d: 1.0 for d in ("factual", "logical", "relevance", "honesty", "adoption")}
    for _ in range(5):
        plain.record_review("t", "echo", good, weight=1.0, same_signal=False)
        sybil.record_review("t", "echo", good, weight=1.0, same_signal=True)
    # 同源刷分被降權 → 觀測累積遠較慢（raises-cost，非 prevents）
    assert sybil.observations("t", "echo") < plain.observations("t", "echo")


def test_ucb_gives_newcomers_exploration():
    # 高分老手 vs 中分新人：UCB 探索額讓新人不被餓死
    veteran = ucb_score(rep_score=0.9, observations=100, total_obs=120)
    newcomer = ucb_score(rep_score=0.5, observations=1, total_obs=120)
    assert newcomer > 0.5  # 探索額把新人抬高
