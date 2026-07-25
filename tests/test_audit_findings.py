"""獨立審查（2026-07-26）發現的缺陷 → 可執行迴歸判準。

每支測試釘死「修補後應有的行為」，並在 docstring 標明對應的 finding 編號與
審查時實測到的錯誤數字。這些測試是**外部可驗證**的：任何人 clone 本 repo、
跑 `pytest tests/test_audit_findings.py` 即可自行確認機制性質，不需要我們的
實驗資料。

設計立場（回應審查 §1）：信任是人給的，系統能提供的是**可究責的身份**——
每個代理的信用必須綁在它自己的記憶鏈上、不可被冒領、不可被他人蒸發，
而懲罰必須真的讓作惡者變差。以下判準就是這幾句話的可執行版本。
"""

from __future__ import annotations

import pytest

from vacant import crypto
from vacant.auditor import Auditor
from vacant.body import CapabilityCard
from vacant.envelope import ReviewEnvelope
from vacant.identity import Identity
from vacant.logbook import Logbook
from vacant.registry import ReviewRejected, Registry
from vacant.reputation import Beta, Reputation, ucb_score
from vacant.research import wilcoxon_signed_rank_exact

FULL = {"factual": 1.0, "logical": 1.0, "relevance": 1.0, "honesty": 1.0, "adoption": 1.0}
ZERO = {k: 0.0 for k in FULL}


class _Book:
    """測試用的居民：真 logbook ＋ 自動附創世證明的能力卡。"""

    def __init__(self, name: str) -> None:
        self.ident = Identity.generate()
        self.book = Logbook()
        self.book.append("GENESIS", {"who": name}, self.ident, ts_ms=0)
        self._ts = 1
        self.card = CapabilityCard(
            vacant_id=self.ident.vacant_id,
            niches=["code"],
            pub_hex=crypto.pub_to_hex(self.ident.pub),
            controller=name,
            stream_id=self.book.stream_id(),
            genesis=self.book.genesis_proof(),
        )

    @property
    def stream_id(self) -> str:
        return self.book.stream_id()

    def head(self) -> str:
        return self.book.head()

    def deliver(self) -> str:
        """交付一筆 → 鏈頭前進，回傳新鏈頭。"""
        self.book.append("DELIVER", {"i": self._ts}, self.ident, ts_ms=self._ts)
        self._ts += 1
        return self.book.head()


def _resident(name: str) -> tuple[Identity, _Book, CapabilityCard]:
    b = _Book(name)
    return b.ident, b, b.card


# ---------------------------------------------------------------------------
# P0-1 slash 的方向性
# ---------------------------------------------------------------------------
class TestSlashDirection:
    """審查實測：破壞者 slash 三次 mean 由 0.0161 升到 0.1053（懲罰變獎勵）。"""

    def test_slash_never_raises_a_low_scorer(self):
        """對已經很爛的 cell 連續 slash，分數必須單調不增。"""
        b = Beta()
        for _ in range(60):
            b.update(0.0, 1.0)
        prev = b.mean
        for _ in range(3):
            b.slash(0.5, now=0)
            assert b.mean <= prev + 1e-12, f"slash 讓低分者上升：{prev} -> {b.mean}"
            prev = b.mean

    def test_slash_does_not_raise_routing_score(self):
        """slash 後 UCB 不得上升——否則被懲罰者反而更容易被派工。

        審查實測：1.0698 -> 1.0895（上升）。"""
        b = Beta()
        for _ in range(60):
            b.update(1.0, 0.9)
        before = ucb_score(b.mean, b.n, total_obs=100.0)
        b.slash(0.5, now=0)
        after = ucb_score(b.mean, b.n, total_obs=100.0)
        assert after <= before + 1e-12, f"slash 抬高了路由分：{before} -> {after}"

    def test_slash_is_not_merely_decay(self):
        """slash(0.5) 不得等價於「老化一個半衰期」——否則牙齒不含懲罰性資訊。"""
        x, y = Beta(), Beta()
        for _ in range(30):
            x.update(1.0, 1.0)
            y.update(1.0, 1.0)
        x.slash(0.5, now=0)
        y.commit_decay(now=200)  # DECAY_HALFLIFE_EVENTS
        assert (abs(x.alpha - y.alpha) > 1e-9 or abs(x.beta - y.beta) > 1e-9), (
            "slash 與 decay 是同一個算子"
        )

    def test_slash_hurts_a_high_scorer_observably(self):
        """高信譽者一次 slash 必須有可觀測下墜（12 §4.2 的原意，要保住）。"""
        b = Beta()
        for _ in range(60):
            b.update(1.0, 1.0)
        before = b.mean
        b.slash(0.5, now=0)
        assert b.mean < before - 0.05, f"高信譽者 slash 後幾乎沒動：{before} -> {b.mean}"

    def test_slash_is_composable(self):
        """兩次 0.5 的效果等於一次 0.25：懲罰的語意必須可疊加、可預測。"""
        a, b = Beta(), Beta()
        for _ in range(40):
            a.update(1.0, 1.0)
            b.update(1.0, 1.0)
        a.slash(0.5, now=0)
        a.slash(0.5, now=0)
        b.slash(0.25, now=0)
        assert a.mean == pytest.approx(b.mean, rel=1e-9)

    def test_slash_keeps_posterior_valid(self):
        """任何 slash 後 α、β 仍是合法 Beta 參數（≥1，先驗不被穿透）。"""
        b = Beta()
        for _ in range(10):
            b.update(0.3, 1.0)
        for f in (0.9, 0.5, 0.1):
            b.slash(f, now=0)
            assert b.alpha >= 1.0 and b.beta >= 1.0
            assert 0.0 <= b.mean <= 1.0


# ---------------------------------------------------------------------------
# P0-3 decay 的時鐘
# ---------------------------------------------------------------------------
class TestDecayClockIsPerStream:
    """審查實測：第三方灌 1500 筆無關 review → 受害者 0.7878/obs 2.71 崩成 0.5037/obs 0.01。"""

    def test_third_party_activity_does_not_erase_my_credit(self):
        rep = Reputation()
        for _ in range(30):
            rep.record_review("mine", "main", "brainA", FULL, weight=1.0)
        before = (rep.score("mine", "main", "brainA"), rep.observations("mine", "main", "brainA"))

        for i in range(1500):  # 攻擊者對「別人的」stream 灌票
            rep.record_review(f"junk{i}", "main", "brainA", FULL, weight=1.0)

        after = (rep.score("mine", "main", "brainA"), rep.observations("mine", "main", "brainA"))
        assert after[0] == pytest.approx(before[0], rel=0.05), (
            f"第三方活動改變了我的分數：{before[0]} -> {after[0]}"
        )
        assert after[1] == pytest.approx(before[1], rel=0.05), (
            f"第三方活動蒸發了我的觀測數：{before[1]} -> {after[1]}"
        )

    def test_own_history_still_decays(self):
        """自己的舊證據仍要隨自己的新事件老化——「信用要一直賺」不能被改掉。"""
        rep = Reputation()
        rep.record_review("s", "main", "brainA", FULL, weight=10.0)
        early = rep.score("s", "main", "brainA")
        for _ in range(400):  # 自己的後續事件（中性偏低）
            rep.record_review("s", "main", "brainA", {k: 0.5 for k in FULL}, weight=0.01)
        assert rep.score("s", "main", "brainA") < early, "自己的歷史完全不 decay"

    def test_pure_query_does_not_create_cells(self):
        """score()/observations() 是查詢，不得有寫入副作用（狀態膨脹向量）。"""
        rep = Reputation()
        rep.score("never-seen", "main", "brainA")
        rep.observations("never-seen", "main", "brainA")
        assert len(rep._cells) == 0


# ---------------------------------------------------------------------------
# P0-2 身份：stream 的擁有權
# ---------------------------------------------------------------------------
class TestStreamOwnership:
    """審查實測：攻擊者宣稱受害者 stream_id → standing 由 (0.5,0.0) 變 (0.7417,1.8708)。"""

    def test_cannot_claim_another_agents_stream(self):
        reg = Registry()
        victim, vbook, vcard = _resident("victim")
        attacker, abook, acard = _resident("attacker")
        reg.announce(vcard)
        reg.announce(acard)
        reg.note_head(victim.vacant_id, vbook.stream_id, "main", vbook.head())

        with pytest.raises(ReviewRejected):
            reg.note_head(attacker.vacant_id, vbook.stream_id, "main", vbook.head())

    def test_transplanted_reputation_is_not_inherited(self):
        reg = Registry()
        victim, vbook, vcard = _resident("victim")
        attacker, abook, acard = _resident("attacker")
        reviewer, rbook, rcard = _resident("reviewer")
        for c in (vcard, acard, rcard):
            reg.announce(c)

        for k in range(20):
            vbook.deliver()
            reg.note_head(victim.vacant_id, vbook.stream_id, "main", vbook.head())
            reg.record_review(ReviewEnvelope.create(
                reviewer, target_id=victim.vacant_id, target_stream_id=vbook.stream_id,
                branch_id="main", target_head=vbook.head(), task_id=f"t{k}",
                substrate="brainA", scores=FULL, ts_ms=k))

        assert reg.standing(victim.vacant_id, "brainA")[1] > 0
        assert reg.standing(attacker.vacant_id, "brainA") == (0.5, 0.0)

    def test_cannot_poison_another_agents_stream(self):
        """對 A 的差評不得寫進 B 的帳。"""
        reg = Registry()
        victim, vbook, vcard = _resident("victim")
        attacker, abook, acard = _resident("attacker")
        reviewer, rbook, rcard = _resident("reviewer")
        for c in (vcard, acard, rcard):
            reg.announce(c)
        vbook.deliver()
        reg.note_head(victim.vacant_id, vbook.stream_id, "main", vbook.head())
        reg.record_review(ReviewEnvelope.create(
            reviewer, target_id=victim.vacant_id, target_stream_id=vbook.stream_id,
            branch_id="main", target_head=vbook.head(), task_id="t0",
            substrate="brainA", scores=FULL, ts_ms=0))
        before = reg.standing(victim.vacant_id, "brainA")

        abook.deliver()
        reg.note_head(attacker.vacant_id, abook.stream_id, "main", abook.head())
        with pytest.raises(ReviewRejected):
            reg.record_review(ReviewEnvelope.create(
                reviewer, target_id=attacker.vacant_id,
                target_stream_id=vbook.stream_id,  # 指向受害者的帳
                branch_id="main", target_head=vbook.head(), task_id="poison",
                substrate="brainA", scores=ZERO, ts_ms=1))
        assert reg.standing(victim.vacant_id, "brainA") == before

    def test_head_cannot_go_backwards(self):
        """回滾（把鏈頭指回舊狀態）必須被拒——否則可挑最有利的歷史呈現。"""
        reg = Registry()
        me, book, card = _resident("me")
        reg.announce(card)
        book.deliver()
        old_head = book.head()
        reg.note_head(me.vacant_id, book.stream_id, "main", old_head)
        book.deliver()
        reg.note_head(me.vacant_id, book.stream_id, "main", book.head())

        with pytest.raises(ReviewRejected):
            reg.note_head(me.vacant_id, book.stream_id, "main", old_head)

    def test_announced_stream_id_must_match_a_real_chain(self):
        """能力卡自稱的 stream_id 必須與實際鏈的創世 hash 一致（可驗證身份）。"""
        reg = Registry()
        me, book, card = _resident("me")
        card.stream_id = "我隨便宣稱的一條鏈"
        with pytest.raises(ValueError):
            reg.announce(card)


# ---------------------------------------------------------------------------
# P1-1 / P1-2 review 的基本衛生
# ---------------------------------------------------------------------------
class TestReviewHygiene:
    def test_self_review_is_rejected(self):
        """自評不得計入信譽（ecosystem / gateway / receipt 都擋，承重層也必須擋）。"""
        reg = Registry()
        me, book, card = _resident("solo")
        reg.announce(card)
        book.deliver()
        reg.note_head(me.vacant_id, book.stream_id, "main", book.head())
        with pytest.raises(ReviewRejected):
            reg.record_review(ReviewEnvelope.create(
                me, target_id=me.vacant_id, target_stream_id=book.stream_id,
                branch_id="main", target_head=book.head(), task_id="self",
                substrate="brainA", scores=FULL, ts_ms=1))

    def test_branch_must_match_observed_head(self):
        """review 的 branch 必須與觀察到的鏈頭一致——否則可寫進任意分支的帳。"""
        reg = Registry()
        target, tbook, tcard = _resident("target")
        rev, rbook, rcard = _resident("rev")
        reg.announce(tcard)
        reg.announce(rcard)
        tbook.deliver()
        reg.note_head(target.vacant_id, tbook.stream_id, "main", tbook.head())
        with pytest.raises(ReviewRejected):
            reg.record_review(ReviewEnvelope.create(
                rev, target_id=target.vacant_id, target_stream_id=tbook.stream_id,
                branch_id="任意分支", target_head=tbook.head(), task_id="x",
                substrate="brainA", scores=FULL, ts_ms=1))

    def test_substrate_must_match_observed_delivery(self):
        """review 的 substrate 必須是交付時觀察到的那顆腦，reviewer 不能自己發明。"""
        reg = Registry()
        target, tbook, tcard = _resident("target")
        rev, rbook, rcard = _resident("rev")
        reg.announce(tcard)
        reg.announce(rcard)
        tbook.deliver()
        reg.note_head(target.vacant_id, tbook.stream_id, "main", tbook.head(), substrate="brainA")
        with pytest.raises(ReviewRejected):
            reg.record_review(ReviewEnvelope.create(
                rev, target_id=target.vacant_id, target_stream_id=tbook.stream_id,
                branch_id="main", target_head=tbook.head(), task_id="x",
                substrate="從未跑過的腦", scores=FULL, ts_ms=1))


# ---------------------------------------------------------------------------
# P1-3 Sybil 的邊際收益
# ---------------------------------------------------------------------------
class TestSybilBounded:
    """審查實測：200 個匿名 sybil 各投一票 → 總權重 10.0（0.05×N 線性）。"""

    @pytest.mark.parametrize("n_sybil", [50, 200])
    def test_anonymous_sybil_gain_is_sublinear(self, n_sybil):
        reg = Registry()
        target, tbook, tcard = _resident("target")
        reg.announce(tcard)
        total = 0.0
        for i in range(n_sybil):
            sybil, sbook, scard = _resident(f"anon-{i}")  # 每人一個不同的自報 controller
            reg.announce(scard)
            tbook.deliver()
            reg.note_head(target.vacant_id, tbook.stream_id, "main", tbook.head())
            total += reg.record_review(ReviewEnvelope.create(
                sybil, target_id=target.vacant_id, target_stream_id=tbook.stream_id,
                branch_id="main", target_head=tbook.head(), task_id=f"s{i}",
                substrate="brainA", scores=FULL, ts_ms=i))
        # log 級上界：0.1·(1+ln N)，與自報 controller 通道同量級
        import math
        bound = 0.1 * (1.0 + math.log(n_sybil))
        assert total <= bound, f"N={n_sybil} 的 sybil 總權重 {total:.2f} 超過 log 級上界 {bound:.2f}"


# ---------------------------------------------------------------------------
# P1-5 見習期是內生的
# ---------------------------------------------------------------------------
class TestProbationIsIntrinsic:
    """審查實測：零觀測外部身分 UCB=20380.9 vs 已證明專家 1.04，且 cap 對它不生效。"""

    def test_unobserved_outsider_cannot_outrank_proven_expert(self):
        reg = Registry()
        expert, ebook, ecard = _resident("expert")
        rev, rbook, rcard = _resident("rev")
        reg.announce(ecard)
        reg.announce(rcard)
        for k in range(30):
            ebook.deliver()
            reg.note_head(expert.vacant_id, ebook.stream_id, "main", ebook.head())
            reg.record_review(ReviewEnvelope.create(
                rev, target_id=expert.vacant_id, target_stream_id=ebook.stream_id,
                branch_id="main", target_head=ebook.head(), task_id=f"e{k}",
                substrate="brainA", scores=FULL, ts_ms=k))
        # 直接 announce、從未被觀測的外部身分（不經 ecosystem 名冊，故不在 _probation 集合）
        outsider, obook, ocard = _resident("outsider")
        reg.announce(ocard)

        picks = [reg.route("code", "brainA").vacant_id for _ in range(9)]  # 避開第 10 筆見習配額
        assert all(p == expert.vacant_id for p in picks), (
            f"未觀測的外部身分搶走了路由：{set(picks)}"
        )


# ---------------------------------------------------------------------------
# P1-6 / P1-7 稽核錨
# ---------------------------------------------------------------------------
class TestAuditAnchor:
    def test_sampling_seed_is_not_a_public_constant(self):
        """兩個獨立建立的 Auditor 不得抽中同一組任務——否則盲區可被預先算出。"""
        a1, a2 = Auditor(rate=0.2), Auditor(rate=0.2)
        tasks = [f"task-{i}" for i in range(200)]
        s1 = {t for t in tasks if a1.should_audit(t)}
        s2 = {t for t in tasks if a2.should_audit(t)}
        assert s1 != s2, "稽核抽樣跨 run 完全相同，盲區是永久的"

    def test_sampling_is_replayable_given_the_seed(self):
        """但同一個 seed 必須完全可重放（記錄紅線：run 包要能重算）。"""
        a1 = Auditor(rate=0.2)
        a2 = Auditor(rate=0.2, seed=a1.seed)
        tasks = [f"task-{i}" for i in range(200)]
        assert [a1.should_audit(t) for t in tasks] == [a2.should_audit(t) for t in tasks]

    def test_infra_failure_is_not_a_provable_fault(self):
        """沙箱跑不起來 ≠ 交付方說謊。基建故障必須是 void，不能變成 slash 的理由。"""
        auditor = Auditor(rate=1.0)
        broken = {"type": "run_python", "code": "assert solve(1) == 1", "timeout": 8}
        rec = auditor.audit(
            task_id="t", target_id="who", answer="```python\ndef solve(x): return x\n```",
            check=broken, claimed_pass=True, ts_ms=0,
            _runner=_raise_infra,  # 注入一個必然拋基建錯誤的 runner
        )
        assert rec.provable_fault is False, "基建故障被誤判成 provable fault"
        assert rec.ran is False, "基建故障應如實記為未稽核（void），不可假裝跑過"


def _raise_infra(_answer: str) -> bool:
    raise OSError("模擬：子行程起不來 / fd 耗盡 / OOM")


# ---------------------------------------------------------------------------
# P0-4 統計
# ---------------------------------------------------------------------------
class TestWilcoxonNormalApprox:
    """審查實測：n=30、20 正 10 負時程式回 p=0.0288 判顯著，精確值 0.0987 不顯著。"""

    def test_all_tied_magnitudes_is_not_falsely_significant(self):
        res = wilcoxon_signed_rank_exact([1.0] * 20 + [-1.0] * 10)
        assert res["p"] >= 0.06, f"tie 修正被重複扣除 → p 過小：{res['p']}"
        assert res["reject"] is False

    def test_matches_sign_test_when_all_magnitudes_tie(self):
        """全 tie 時 signed-rank 退化為符號檢定，兩者應同量級。"""
        import math
        n_pos, n = 20, 30
        exact = 2 * sum(math.comb(n, k) for k in range(n_pos, n + 1)) / 2 ** n
        got = wilcoxon_signed_rank_exact([1.0] * n_pos + [-1.0] * (n - n_pos))["p"]
        assert got == pytest.approx(exact, abs=0.04), f"常態近似偏離精確值：{got} vs {exact}"

    def test_no_ties_branch_unaffected(self):
        """無 tie 時的常態近似不得被修補弄壞。"""
        diffs = [float(i) for i in range(1, 31)]
        res = wilcoxon_signed_rank_exact(diffs)
        assert res["method"] == "normal_approx"
        assert res["p"] < 0.001  # 全正、量值互異 → 極顯著


# ---------------------------------------------------------------------------
# P2 人類仲裁：說了就要做，但不能無中生有
# ---------------------------------------------------------------------------
class TestHumanArbitrationHasTeeth:
    """審查實測：report(FAIL) 只發 SLASH 事件、從不呼叫 apply_slash，
    而 demo 對人類印的是「記帳並下墜信用」——說了卻沒做。"""

    def _eco(self, tmp_path):
        from vacant.ecosystem import DemoBrain, Ecosystem
        eco = Ecosystem(tmp_path, DemoBrain(), root_mode="demo")
        eco.toggle(True)
        r = eco.delegate("寫 solve(nums)", {
            "type": "run_python", "code": "assert solve([1]) == 1", "timeout": 8})
        return eco, r

    def test_corroborated_fail_actually_moves_credit(self, tmp_path):
        eco, r = self._eco(tmp_path)
        card = r["trust_card"]
        assert card["audit"]["performed"] and card["audit"]["passed"] is False, (
            "前提：這筆交付已被確定性稽核抓到"
        )
        name = card["deliverer"]["name"]
        vid = eco.residents[name].vacant_id
        before = eco.registry.standing(vid, eco.substrate_id)[0]
        out = eco.report(r["task_id"], "FAIL", evidence="objective check failed at audit")
        assert out["credit_applied"] is True
        assert eco.registry.standing(vid, eco.substrate_id)[0] < before

    def test_uncorroborated_accusation_cannot_move_credit(self, tmp_path):
        """稽核沒抓到的指控不得扣分——否則未認證的通道就是毀人信譽的入口。"""
        eco, r = self._eco(tmp_path)
        card = r["trust_card"]
        card["audit"] = {"performed": True, "passed": True}  # 假裝這筆通過了稽核
        eco._cards[r["task_id"]] = card
        name = card["deliverer"]["name"]
        vid = eco.residents[name].vacant_id
        before = eco.registry.standing(vid, eco.substrate_id)[0]
        out = eco.report(r["task_id"], "FAIL", evidence="我說他錯了")
        assert out["credit_applied"] is False
        assert eco.registry.standing(vid, eco.substrate_id)[0] == before

    def test_unknown_task_still_rejected(self, tmp_path):
        eco, _r = self._eco(tmp_path)
        out = eco.report("deadbeef", "FAIL")
        assert out["ack"] is False
