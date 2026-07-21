"""credit-memory v1 改動1＋改動3 的直接覆蓋。

改動1：logbook 綁 stream_id/branch_id、真 head()。
改動3：signed ReviewEnvelope——record_review 只收驗簽＋head 新鮮＋去重，
weight 內生、同源非線性降權（floor/k）。
對應 06/v1_credit-memory規格 §2、§3 攻擊表。
"""

import pytest

from vacant.body import now_ms
from vacant.envelope import ReviewEnvelope
from vacant.host import Host
from vacant.identity import Identity, PublicIdentity
from vacant.logbook import EMPTY_PREV_HASH, GENESIS_STREAM_ID, Logbook
from vacant.registry import REVIEWER_WEIGHT_FLOOR, ReviewRejected
from vacant.reputation import DIMS, SAME_SIGNAL_FLOOR
from vacant.substrate import EchoSubstrate

GOOD = {d: 1.0 for d in DIMS}


def _idn() -> Identity:
    return Identity.generate()


# === 改動1：logbook stream/branch/head ======================================

def test_stream_id_is_genesis_hash_and_head_advances():
    idn = _idn()
    lb = Logbook()
    assert lb.stream_id() is None
    assert lb.head() == EMPTY_PREV_HASH
    e1 = lb.append("BIRTH", {"hello": 1}, idn, ts_ms=1)
    assert e1.stream_id == GENESIS_STREAM_ID  # 創世事件的欄位是佔位
    assert lb.stream_id() == e1.hash()        # stream 身份＝創世事件 hash
    assert lb.head() == e1.hash()
    e2 = lb.append("WORK", {"x": 2}, idn, ts_ms=2)
    assert e2.stream_id == e1.hash()          # 後續事件綁定 stream 身份
    assert e2.branch_id == "main"
    assert lb.head() == e2.hash()


def test_signature_covers_stream_and_branch():
    idn = _idn()
    lb = Logbook()
    lb.append("BIRTH", {}, idn, ts_ms=1)
    lb.append("WORK", {}, idn, ts_ms=2)
    pub = PublicIdentity(idn.vacant_id, idn.pub)
    assert lb.verify_chain(pub)
    # 竄改 stream_id / branch_id → 驗鏈必失敗（簽章與 hash 都涵蓋）
    lb.entries[1].stream_id = "f" * 64
    assert not lb.verify_chain(pub)


def test_branch_tamper_detected():
    idn = _idn()
    lb = Logbook()
    lb.append("BIRTH", {}, idn, ts_ms=1)
    lb.append("WORK", {}, idn, ts_ms=2)
    lb.entries[1].branch_id = "evil"
    assert not lb.verify_chain(PublicIdentity(idn.vacant_id, idn.pub))


def test_old_wire_format_rejected():
    from vacant.logbook import LogEntry
    with pytest.raises(ValueError):
        LogEntry.from_json({"seq": 1, "prev_hash": "0" * 64, "ts_ms": 1,
                            "type": "BIRTH", "payload": {}, "sig": "00"})


def test_roundtrip_save_load_verifies(tmp_path):
    idn = _idn()
    lb = Logbook()
    lb.append("BIRTH", {}, idn, ts_ms=1)
    lb.append("WORK", {"a": 1}, idn, ts_ms=2)
    p = tmp_path / "lb.ndjson"
    lb.save(p)
    lb2 = Logbook.load(p)
    assert lb2.verify_chain(PublicIdentity(idn.vacant_id, idn.pub))
    assert lb2.stream_id() == lb.stream_id()
    assert lb2.head() == lb.head()


# === 改動3：ReviewEnvelope ===================================================

def _review(reviewer: Identity, *, target_id="t", stream="s" * 64, head="h" * 64,
            branch="main", task_id="task1", substrate="echo", scores=GOOD):
    return ReviewEnvelope.create(
        reviewer, target_id=target_id, target_stream_id=stream, branch_id=branch,
        target_head=head, task_id=task_id, substrate=substrate, scores=scores,
        ts_ms=now_ms(),
    )


def test_review_sig_verifies_and_binds_reviewer():
    r = _idn()
    env = _review(r)
    assert env.verify_sig(PublicIdentity(r.vacant_id, r.pub))
    other = _idn()
    assert not env.verify_sig(PublicIdentity(other.vacant_id, other.pub))


def test_review_sig_covers_stream_head_task():
    """v1 §3 攻擊表第一列：舊 review 簽章搬到新 stream / 新 head → 驗章失敗。"""
    r = _idn()
    env = _review(r)
    pub = PublicIdentity(r.vacant_id, r.pub)
    for field, val in (("target_stream_id", "x" * 64), ("target_head", "y" * 64),
                       ("branch_id", "fork"), ("task_id", "task2"),
                       ("target_id", "other"), ("substrate", "brain-b")):
        moved = ReviewEnvelope.from_json({**env.to_json(), field: val})
        assert not moved.verify_sig(pub), f"搬移 {field} 後仍驗過＝簽章沒涵蓋它"


def test_review_from_json_validates():
    r = _idn()
    d = _review(r).to_json()
    with pytest.raises(ValueError):
        ReviewEnvelope.from_json({**d, "scores": {"factual": 2.0}})  # 超界
    with pytest.raises(ValueError):
        ReviewEnvelope.from_json({k: v for k, v in d.items() if k != "target_head"})


# === 改動3：registry.record_review 驗收鏈 ====================================

def _eco(tmp_path):
    """一個最小生態：requester＋expert，先跑一筆真交付讓 registry 記到 head。"""
    h = Host(tmp_path, substrate=EchoSubstrate(p_base=1.0))
    req = h.mint("requester", niches=[])
    h.mint("expert", niches=["reverse"])
    task = {"task_id": "t1", "niche": "reverse", "input": "abc", "expected": "cba",
            "prompt": "[reverse] abc", "check": lambda a: str(a) == "cba"}
    oc = req.call("reverse", task)
    return h, req, oc


def test_gateway_review_is_signed_and_recorded(tmp_path):
    h, req, oc = _eco(tmp_path)
    # 交付後 reputation 有觀測（review 走了簽章通道且被收；改動2：三元組查找）
    _st, _br, _hd = h.registry._heads[oc.callee_id]
    assert h.registry._rep.observations(_st, _br, oc.substrate) > 0
    # result envelope 附了 stream 身份與鏈頭
    assert oc.result_env.body["chain_head"]
    assert oc.result_env.body["stream_id"]


def test_unannounced_reviewer_rejected(tmp_path):
    h, req, oc = _eco(tmp_path)
    ghost = _idn()  # 沒 announce 過的身份
    stream, _br, head = h.registry._heads[oc.callee_id]
    env = _review(ghost, target_id=oc.callee_id, stream=stream, head=head,
                  substrate=oc.substrate)
    with pytest.raises(ReviewRejected):
        h.registry.record_review(env)


def test_bad_signature_rejected(tmp_path):
    h, req, oc = _eco(tmp_path)
    stream, _br, head = h.registry._heads[oc.callee_id]
    reviewer = h.body("requester").identity
    env = _review(reviewer, target_id=oc.callee_id, stream=stream, head=head,
                  substrate=oc.substrate, task_id="t2")
    forged = ReviewEnvelope.from_json({**env.to_json(), "scores": {d: 0.0 for d in DIMS}})
    with pytest.raises(ReviewRejected):
        h.registry.record_review(forged)


def test_stale_head_rejected(tmp_path):
    h, req, oc = _eco(tmp_path)
    stream, _br, _head = h.registry._heads[oc.callee_id]
    reviewer = h.body("requester").identity
    env = _review(reviewer, target_id=oc.callee_id, stream=stream, head="0" * 64,
                  substrate=oc.substrate, task_id="t2")
    with pytest.raises(ReviewRejected):
        h.registry.record_review(env)


def test_duplicate_review_rejected(tmp_path):
    """(reviewer, stream, head) 去重防重放。"""
    h, req, oc = _eco(tmp_path)
    stream, _br, head = h.registry._heads[oc.callee_id]
    reviewer = h.body("requester").identity
    env = _review(reviewer, target_id=oc.callee_id, stream=stream, head=head,
                  substrate=oc.substrate, task_id="t2")
    with pytest.raises(ReviewRejected):  # gateway.call 已對同 head 記過一筆
        h.registry.record_review(env)


def test_weight_is_endogenous_new_reviewer_near_zero(tmp_path):
    """v1 改動3.3：全新 Sybil reviewer 的 weight ≈ 地板（不接受外部注入）。"""
    h, req, oc = _eco(tmp_path)
    # sybil 有公告（拿得到身份）但零被審歷史
    h.mint("sybil", niches=[])
    sybil = h.body("sybil").identity
    stream, _br, head = h.registry._heads[oc.callee_id]
    # 讓 head 前進一筆，避開 gateway 已記的去重鍵
    h.registry.note_head(oc.callee_id, stream, _br, "e" * 64)
    env = _review(sybil, target_id=oc.callee_id, stream=stream, head="e" * 64,
                  substrate=oc.substrate, task_id="t3")
    w = h.registry.record_review(env)
    assert w == pytest.approx(REVIEWER_WEIGHT_FLOOR)


def test_same_source_nonlinear_downweight(tmp_path):
    """v1 改動3.4：同 controller 第 k 筆 review 權重 ≤ floor/k（總貢獻 log 級）。"""
    h = Host(tmp_path, substrate=EchoSubstrate(p_base=1.0))
    h.mint("target", niches=["reverse"], controller="mallory")
    tid = h.vacant_id("target")
    h.registry.note_head(tid, "s" * 64, "main", "h" * 64)
    weights = []
    for i in range(3):
        h.mint(f"shill_{i}", niches=[], controller="mallory")
        shill = h.body(f"shill_{i}").identity
        h.registry.note_head(tid, "s" * 64, "main", f"{i}{'h' * 63}")
        env = _review(shill, target_id=tid, stream="s" * 64, head=f"{i}{'h' * 63}",
                      substrate="echo", task_id=f"t{i}")
        weights.append(h.registry.record_review(env))
    assert weights[0] <= SAME_SIGNAL_FLOOR
    assert weights[1] <= SAME_SIGNAL_FLOOR / 2
    assert weights[2] <= SAME_SIGNAL_FLOOR / 3


# === 改動2：reputation key＝(stream_id, branch_id, substrate) =================

def test_credit_follows_stream_not_body(tmp_path):
    """改動2 承重語意：credit 跟著記憶走，不跟身體走。

    同一把 key（同一 vacant_id）：stream A 攢的信用，在解析表切到新 stream B
    （＝wipe 後的新創世）後**自然歸零**——不需要任何抹除動作，這正是 key 換成
    三元組要達成的行為（06 §2；15 §1 B8）。"""
    h = Host(tmp_path, substrate=EchoSubstrate(p_base=1.0))
    h.mint("worker", niches=["reverse"])
    vid = h.vacant_id("worker")
    reviewer = _idn()
    # stream A 上攢 5 筆好評（head 每筆前進以免去重）
    for i in range(5):
        h.registry.note_head(vid, "streamA", "main", f"{i}{'a' * 63}")
        env = _review(reviewer, target_id=vid, stream="streamA", head=f"{i}{'a' * 63}",
                      substrate="echo", task_id=f"tA{i}")
        # reviewer 未公告 → 拒收；先公告一張卡
        if i == 0:
            from vacant.body import CapabilityCard
            from vacant import crypto
            h.registry.announce(CapabilityCard(
                vacant_id=reviewer.vacant_id, niches=[],
                pub_hex=crypto.pub_to_hex(reviewer.pub)))
        h.registry.record_review(env)
    score_a, obs_a = h.registry.standing(vid, "echo")
    assert obs_a > 0 and score_a > 0.5  # stream A 有信用

    # wipe：同一把 key、新創世 → 解析表切到 stream B
    h.registry.note_head(vid, "streamB", "main", "b" * 64)
    score_b, obs_b = h.registry.standing(vid, "echo")
    assert (score_b, obs_b) == (0.5, 0.0)  # 信用歸零（新三元組＝空格）

    # 舊 stream A 的格子還在（歷史不滅），但不再被解析到——帳在、信用不續
    assert h.registry._rep.observations("streamA", "main", "echo") > 0


def test_reputation_json_roundtrip_triple_key():
    """三元組序列化 round-trip（␟ 分隔；改動2 後的線材格式）。"""
    from vacant.reputation import Reputation
    rep = Reputation()
    rep.record_review("s1", "main", "echo", GOOD, weight=1.0)
    rep.record_review("s1", "fork", "echo", {d: 0.0 for d in DIMS}, weight=1.0)
    d = rep.to_json()
    assert d["event_seq"] == 2  # 兩筆 review 推進全局事件序（decay 時間軸）
    assert set(d["cells"]) == {"s1␟main␟echo", "s1␟fork␟echo"}
    rep2 = Reputation.from_json(d)
    assert rep2.score("s1", "main", "echo") > 0.5
    assert rep2.score("s1", "fork", "echo") < 0.5
