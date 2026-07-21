"""G4/G5/G6 驗收：閘道把關（冒名/replay/低信譽被拒）+ 信譽路由。"""

from __future__ import annotations

import pytest

from vacant.body import now_ms
from vacant.envelope import Envelope, ReplayError
from vacant.gateway import BadSignature, ReputationRejected
from vacant.host import Host
from vacant.identity import Identity
from vacant.substrate import EchoSubstrate
from vacant.tasks import make_task


def _host(tmp_path, p_base=1.0):
    return Host(tmp_path, substrate=EchoSubstrate(p_base=p_base))


# --- G5：完整 call 迴圈成立 --------------------------------------------------
def test_full_call_loop_correct(tmp_path):
    h = _host(tmp_path)
    req = h.mint("requester", niches=[])
    h.mint("expert", niches=["reverse"])
    task = make_task(0, "reverse")
    out = req.call("reverse", task)
    assert out.correct is True
    assert task["check"](out.answer)
    # 互動雙方 logbook 都可驗
    assert h.body("requester").logbook.verify_chain(h.body("requester").public_identity())
    assert h.body("expert").logbook.verify_chain(h.body("expert").public_identity())


# --- G4：冒名被拒 ------------------------------------------------------------
def test_ingress_rejects_impersonation(tmp_path):
    h = _host(tmp_path)
    h.mint("requester", niches=[])
    expert = h.mint("expert", niches=["reverse"])
    mallory = Identity.generate()  # 未登錄、且想冒充 requester
    real_req_id = h.vacant_id("requester")
    forged = Envelope.create(
        mallory, to=expert.vacant_id, seq=1, prev_hash="0" * 64, ts_ms=now_ms(),
        kind="call", body={"prompt": "x", "task_id": "t", "niche": "reverse", "input": "ab"},
    )
    forged.frm = real_req_id  # 偽造寄件者 = requester，但簽章是 mallory 的
    with pytest.raises(BadSignature):
        expert.ingress(forged)


def test_ingress_rejects_unknown_sender(tmp_path):
    h = _host(tmp_path)
    expert = h.mint("expert", niches=["reverse"])
    ghost = Identity.generate()  # 從未在 halo 公告
    env = Envelope.create(
        ghost, to=expert.vacant_id, seq=1, prev_hash="0" * 64, ts_ms=now_ms(),
        kind="call", body={"prompt": "x", "task_id": "t", "niche": "reverse", "input": "ab"},
    )
    with pytest.raises(BadSignature):
        expert.ingress(env)


# --- Codex Bug 1：registry 必須驗身份綁定（vacant_id↔pubkey）---------------
def test_registry_rejects_forged_identity_binding(tmp_path):
    from vacant.body import CapabilityCard
    h = _host(tmp_path)
    victim = h.mint("victim", niches=["reverse"])
    attacker = Identity.generate()
    # 攻擊者想用「受害者的 vacant_id + 自己的 pubkey」污染 registry → 冒名
    forged_card = CapabilityCard(
        vacant_id=victim.vacant_id,           # 別人的 id
        niches=["reverse"],
        pub_hex=__import__("vacant").crypto.pub_to_hex(attacker.pub),  # 自己的 key
    )
    with pytest.raises(ValueError):
        h.registry.announce(forged_card)


# --- Codex Bug 2：ingress 必須拒絕「不是寄給我」的信封 ---------------------
def test_ingress_rejects_wrong_recipient(tmp_path):
    h = _host(tmp_path)
    req = h.mint("requester", niches=[])
    a = h.mint("expert_a", niches=["reverse"])
    h.mint("expert_b", niches=["reverse"])
    body = h.body("requester")
    # 簽一封「寄給 expert_b」的信封，卻投遞給 expert_a
    env = Envelope.create(
        body.identity, to=h.vacant_id("expert_b"), seq=1, prev_hash="0" * 64,
        ts_ms=now_ms(), kind="call",
        body={"prompt": "[reverse] ab", "task_id": "t", "niche": "reverse", "input": "ab"},
    )
    with pytest.raises(BadSignature):
        a.ingress(env)


# --- G4：replay 被拒 ---------------------------------------------------------
def test_ingress_rejects_replay(tmp_path):
    h = _host(tmp_path)
    req = h.mint("requester", niches=[])
    expert = h.mint("expert", niches=["reverse"])
    task = make_task(0, "reverse")
    # 正常送一次（透過 egress 簽好 seq=1）
    req.call("reverse", task)
    # 攔截下「同一個 seq=1 的 call 信封」重送 → ingress_guard 應抓到
    seq, prev = req.egress_guard.next_seq(expert.vacant_id)  # 這是 seq=2 的視角
    # 重建 seq=1 重放
    body = h.body("requester")
    replay = Envelope.create(
        body.identity, to=expert.vacant_id, seq=1, prev_hash="0" * 64, ts_ms=now_ms(),
        kind="call", body={"prompt": task["prompt"], "task_id": task["task_id"], "niche": "reverse", "input": task["input"]},
    )
    with pytest.raises(ReplayError):
        expert.ingress(replay)


# --- G4：低信譽被拒 ----------------------------------------------------------
def test_ingress_rejects_low_reputation_caller(tmp_path):
    h = _host(tmp_path)
    req = h.mint("requester", niches=[])
    expert = h.mint("expert", niches=["reverse"])
    # 人為把 requester（當作 target）打成 known-bad，超過把關觀測門檻。
    # （改動3 後 record_review 只收簽章 ReviewEnvelope；這裡測的是「把關」不是
    # review 驗收，直接灌內部 reputation 當測試 seeding。改動2：三元組 key＋
    # note_head 解析表，standing 才找得到這格。）
    rid = h.vacant_id("requester")
    h.registry.note_head(rid, rid, "main", "h" * 64)  # 空鏈慣例：stream＝vacant_id
    for _ in range(5):
        h.registry._rep.record_review(
            rid, "main", EchoSubstrate().substrate_id,
            {"factual": 0.0, "logical": 0.0, "relevance": 0.0, "honesty": 0.0, "adoption": 0.0},
        )
    task = make_task(0, "reverse")
    with pytest.raises(ReputationRejected):
        req.call("reverse", task)


# --- 審查修補：經閘道自呼被拒（避免同一身體被覆蓋）-------------------------
def test_self_call_rejected(tmp_path):
    h = _host(tmp_path)
    solo = h.mint("solo", niches=["reverse"])  # 自己既是 caller 又是唯一 expert
    with pytest.raises(ValueError):
        solo.call("reverse", make_task(0, "reverse"))


# --- 審查修補：對端 ingress 丟例外時，caller 的 A2A_OUT 仍落地 -------------
def test_caller_body_persisted_even_when_ingress_fails(tmp_path):
    h = _host(tmp_path)
    req = h.mint("requester", niches=[])
    expert = h.mint("expert", niches=["reverse"])
    # 把 requester 打成 known-bad → 對端 ingress 會丟 ReputationRejected
    # （直接灌內部 reputation 當測試 seeding，見上一測試的註解；改動2 三元組）
    rid = h.vacant_id("requester")
    h.registry.note_head(rid, rid, "main", "h" * 64)
    for _ in range(5):
        h.registry._rep.record_review(
            rid, "main", EchoSubstrate().substrate_id,
            {"factual": 0.0, "logical": 0.0, "relevance": 0.0, "honesty": 0.0, "adoption": 0.0},
        )
    with pytest.raises(ReputationRejected):
        req.call("reverse", make_task(0, "reverse"))
    # 例外後：caller 的 A2A_OUT 應已持久化，且鏈仍可驗（與 egress seq 一致）
    body = h.body("requester")
    assert any(e.type == "A2A_OUT" for e in body.logbook.entries)
    assert body.logbook.verify_chain(body.public_identity())


# --- 審查修補：信譽把關用「本顆腦」口徑，不被別顆腦的好成績矇混 -----------
def test_ingress_gate_is_substrate_specific(tmp_path):
    h = _host(tmp_path)
    req = h.mint("requester", niches=[])
    expert = h.mint("expert", niches=["reverse"])
    rid = h.vacant_id("requester")
    cur = EchoSubstrate().substrate_id  # 當前這顆腦
    # 在「別顆腦」上刷一堆好評（足以拉高跨腦平均），但當前這顆腦上是 known-bad
    # （直接灌內部 reputation 當測試 seeding，見上面的註解；改動2 三元組＋解析表）
    h.registry.note_head(rid, rid, "main", "h" * 64)
    for _ in range(8):
        h.registry._rep.record_review(rid, "main", "other-brain", {d: 1.0 for d in (
            "factual", "logical", "relevance", "honesty", "adoption")})
    for _ in range(5):
        h.registry._rep.record_review(rid, "main", cur, {d: 0.0 for d in (
            "factual", "logical", "relevance", "honesty", "adoption")})
    # 跨腦平均會放行，但 substrate-specific 口徑應擋下
    with pytest.raises(ReputationRejected):
        req.call("reverse", make_task(0, "reverse"))


# --- G6：信譽路由挑到有履歷的專家 -------------------------------------------
def test_reputation_routing_prefers_proven_expert(tmp_path):
    # good 永遠解對；bad 永遠解錯 → 幾輪後路由應收斂到 good
    class Mixed(EchoSubstrate):
        def run(self, home, prompt, task):
            from vacant.substrate import SubstrateResult
            from vacant.tasks import NICHE_SOLVERS
            if "bad" in home.parent.name:  # home = <root>/<name>/home → 取 vacant 名
                return SubstrateResult(output="[wrong]", substrate_id=self.substrate_id, learned_skill=None)
            return SubstrateResult(output=str(NICHE_SOLVERS[task["niche"]](task["input"])), substrate_id=self.substrate_id, learned_skill=None)

    h = Host(tmp_path, substrate=Mixed())
    req = h.mint("requester", niches=[])
    h.mint("good_expert", niches=["reverse"])
    h.mint("bad_expert", niches=["reverse"])

    picks = []
    for i in range(40):
        out = req.call("reverse", make_task(i, "reverse"))
        picks.append(out.callee_id)

    good_id = h.vacant_id("good_expert")
    bad_id = h.vacant_id("bad_expert")
    # 整體偏好 good（含早期探索）
    assert picks.count(good_id) > picks.count(bad_id)
    # 收斂：後半段大多路由到 good（容許 UCB 偶爾再探索 bad）
    assert picks[-20:].count(good_id) >= 14
    board = h.registry.leaderboard("reverse", Mixed().substrate_id)
    assert board[0][0] == good_id  # 排行榜第一是 good
