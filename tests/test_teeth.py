"""牙齒（12 §4.2；17 §P4）：decay／slash／probation 的**路由端真後果**。

對應 13 §2 A-W1 門：decay 半衰期、slash 乘法扣減、probation 權重上限——
各有手算對照（對照值寫進測試註解）。也對應 B 層情境③④⑤的單元級前題；
六情境的端到端掃描在 vacant/blayer.py。
"""

from __future__ import annotations

import pytest

from vacant import registry as registry_mod
from vacant.body import CapabilityCard
from vacant.registry import PROBATION_SCORE_CAP, Registry
from vacant.reputation import DIMS, Beta, Reputation

GOOD = {d: 1.0 for d in DIMS}
KEY = ("streamX", "main", "echo")


# --- decay：半衰期 200 事件、向先驗回歸 ----------------------------------------
class TestDecay:
    def test_halflife_200_hand_computed(self):
        """手算：1 筆全好評後 α=2,β=1（mean 2/3）；老化 200 事件 f=0.5 →
        α=1.5,β=1 → mean=1.5/2.5=0.6；再 200 事件 f=0.25 → α=1.25 → 1.25/2.25≈0.5556。

        時間軸是**該 stream 自己的事件序**（獨立審查 P0-3 後的語意），所以
        半衰期算術直接對 Beta 驗；Reputation 層的時鐘歸屬另由下一支測試釘死。"""
        b = Beta()
        b.update(1.0, 1.0)
        assert b.mean == pytest.approx(2 / 3)
        b.commit_decay(now=200)
        assert b.mean == pytest.approx(0.6)
        b.commit_decay(now=400)
        assert b.mean == pytest.approx(1.25 / 2.25)

    def test_decay_clock_is_per_stream_not_global(self):
        """別人的活動不得推進我的 decay 時鐘（獨立審查 P0-3）。

        改動前：event_seq 是全帳本共用，任何人灌票都會把全網信譽拉回先驗、
        把有效觀測數清成 0（實測 0.788/obs 2.71 → 0.504/obs 0.01）。"""
        rep = Reputation()
        rep.record_review(*KEY, GOOD, weight=1.0)
        before = (rep.score(*KEY), rep.observations(*KEY))
        for _ in range(400):  # 別處的 400 筆 review
            rep.record_review("other", "main", "echo", GOOD, weight=1.0)
        assert (rep.score(*KEY), rep.observations(*KEY)) == before

    def test_decay_toward_prior_not_zero(self):
        """壞評也往 0.5 回歸（先驗是吸引子）；觀測數同步衰減（UCB 探索回溫）。

        「一直賺」的語意保留在自己的時間軸上：用本 stream 自己的後續事件推進。"""
        rep = Reputation()
        for _ in range(10):
            rep.record_review(*KEY, {d: 0.0 for d in DIMS}, weight=1.0)
        low = rep.score(*KEY)
        low_obs = rep.observations(*KEY)
        assert low < 0.2
        for _ in range(200):  # 本 stream 自己的後續事件（極小權重，只推時鐘）
            rep.record_review(*KEY, {d: 0.5 for d in DIMS}, weight=1e-6)
        assert rep.score(*KEY) > low            # 往先驗回升
        assert rep.observations(*KEY) < low_obs  # 觀測衰減：舊帳的「確定度」也在消退

    def test_beta_slash_validation(self):
        with pytest.raises(ValueError):
            Beta().slash(0.0, now=0)
        with pytest.raises(ValueError):
            Beta().slash(1.5, now=0)


# --- slash：乘法扣減、誤放行罰重於誤攔 ------------------------------------------
class TestSlash:
    def test_deliverer_multiplicative_hand_computed(self):
        """手算：單筆 weight=10 好評 → α=11,β=1（mean 11/12≈0.9167；slash 不推進
        時鐘，排除 decay 對算術的干擾）。

        slash 的語意是「把後驗均值乘以 factor」，實作＝注入負面證據
        β += (α+β)(1/factor−1)（獨立審查 P0-1；舊版 α、β 同乘會保持證據比不變，
        對低分者反而是加分）：
          第一次 ×0.5 → β += 12 → 11/24 ≈ 0.4583（＝ 11/12 的一半）
          第二次 ×0.5 → β += 24 → 11/48 ≈ 0.2292（＝ 11/12 的四分之一）"""
        rep = Reputation()
        rep.record_review(*KEY, GOOD, weight=10.0)
        assert rep.score(*KEY) == pytest.approx(11 / 12)
        rep.slash(*KEY, 0.5)
        assert rep.score(*KEY) == pytest.approx(11 / 24)
        rep.slash(*KEY, 0.5)
        assert rep.score(*KEY) == pytest.approx(11 / 48)

    def test_slash_punishes_monotonically(self):
        """對任何起始狀態，slash 都必須讓分數下降——包含已經很低的那些。

        舊實作對 60 筆 0 分的破壞者 slash 三次，分數是 0.016→0.031→0.059→0.105
        （越罰越高）。這條是那個缺陷的守門測試。"""
        rep = Reputation()
        for _ in range(60):
            rep.record_review(*KEY, {d: 0.0 for d in DIMS}, weight=1.0)
        prev = rep.score(*KEY)
        for _ in range(3):
            rep.slash(*KEY, 0.5)
            now = rep.score(*KEY)
            assert now < prev, f"slash 讓低分者上升：{prev} -> {now}"
            prev = now

    def test_dims_scoped_slash(self):
        """reviewer 入押只扣 honesty：其他維不動（預期曲線的單元級）。"""
        rep = Reputation()
        for _ in range(5):
            rep.record_review(*KEY, GOOD, weight=1.0)
        before = rep.score(*KEY)
        rep.slash(*KEY, 0.5, dims=("honesty",))
        cell = rep.cell(*KEY)
        assert cell.dims["honesty"].mean < cell.dims["factual"].mean
        assert rep.score(*KEY) < before  # 總分下降但不塌（單維扣減）


# --- probation：路由端權重上限 ----------------------------------------------------
class TestProbationTeeth:
    def _registry_with_two(self) -> tuple[Registry, str, str]:
        reg = Registry()
        vet = CapabilityCard(vacant_id="veteran", niches=["code"], pub_hex="")
        new = CapabilityCard(vacant_id="newbie", niches=["code"], pub_hex="")
        reg._cards = {"veteran": vet, "newbie": new}  # 繞過 announce 的 pub 檢查（單元測路由）
        # veteran 有 10 筆好評（高分）；newbie 全新（UCB 探索額極大）
        reg.note_head("veteran", "sV", "main", "h" * 64)
        for i in range(10):
            reg._rep.record_review("sV", "main", "echo", GOOD, weight=1.0)
        return reg, "veteran", "newbie"

    def test_probation_caps_ucb_so_veteran_wins(self, monkeypatch):
        """見習生 UCB 被蓋到 0.55：沒這個蓋子，obs=0 的探索額會讓新人必贏。
        （route_seq 未滿 10 → 見習配額不觸發，測的是蓋子本身。）

        見習判準現在是**內生**的（獨立審查 P1-5）：自身觀測 < PROBATION_MIN_OBS
        即為見習，不再只看外部集合——否則任何直接 announce 的身分都不受約束。
        因此反事實要靠把內生門檻降到 0 來表達，而不是清空外部集合。"""
        reg, vet, new = self._registry_with_two()
        # 反事實：拆掉蓋子（內生門檻歸零＋不在外部集合）→ 新人靠探索額必贏
        monkeypatch.setattr(registry_mod, "PROBATION_MIN_OBS", 0.0)
        assert reg.route("code", "echo").vacant_id == new
        monkeypatch.undo()
        assert reg.route("code", "echo").vacant_id == vet  # 內生見習判準即生效
        reg.set_probation(new, True)
        assert reg.route("code", "echo").vacant_id == vet  # 外部標記可疊加

    def test_probation_is_intrinsic_for_unregistered_outsiders(self):
        """未經 ecosystem 名冊、直接 announce 的零觀測身分同樣被蓋。

        改動前：_probation 只由 ecosystem 依交付數同步，外部身分永遠不在集合裡，
        而零觀測候選 UCB 是天文數字（實測 20380.9 vs 已證明專家 1.04）。"""
        reg, vet, _new = self._registry_with_two()
        reg._cards["outsider"] = CapabilityCard(
            vacant_id="outsider", niches=["code"], pub_hex="")
        assert reg.in_probation("outsider", "echo") is True
        assert reg.route("code", "echo").vacant_id == vet

    def test_probation_quota_every_10th_route(self):
        """見習配額（防永久流放）：veteran 壟斷 9 筆，第 10 筆路由留給見習生——
        m 筆強制稽核因此真的會發生（X4 洗白成本的前提）。"""
        reg, vet, new = self._registry_with_two()
        reg.set_probation(new, True)
        picks = [reg.route("code", "echo").vacant_id for _ in range(10)]
        assert picks[:9] == [vet] * 9   # 蓋子讓老手拿走常態份額
        assert picks[9] == new          # 第 10 筆＝見習配額

    def test_all_probation_no_cap_cold_start(self):
        """全員見習 → 不蓋（冷啟動保護）：新生態的 UCB 探索不受牙齒壓制。"""
        reg, _, new = self._registry_with_two()
        reg.set_probation("veteran", True)
        reg.set_probation(new, True)
        # 全見習時不蓋 → obs=0 的新人探索額照常生效
        assert reg.route("code", "echo").vacant_id == new

    def test_cap_value_is_prereg_constant(self):
        assert PROBATION_SCORE_CAP == 0.55
        # 蓋子高於中性 0.5：新人仍可被探索、只是不能壓過已證明者（raises-cost）
        assert 0.5 < PROBATION_SCORE_CAP < 0.9


# --- slash 的路由端傳導（apply_slash 經解析表）------------------------------------
class TestSlashRouting:
    def test_apply_slash_hits_current_stream(self):
        reg, _, _ = TestProbationTeeth()._registry_with_two()
        assert reg.apply_slash("veteran", "echo", 0.5) is True
        score, _ = reg.standing("veteran", "echo")
        assert score < 0.9  # 下墜可觀測（對照舊版「只增不減」）
        assert reg.apply_slash("nobody", "echo", 0.5) is False  # 未解析→如實 False


# --- ecosystem 端到端：provable fault 的真扣分 -------------------------------------
class TestEcosystemTeeth:
    def test_provable_fault_slashes_deliverer_and_pass_reviewer(self, tmp_path):
        """saboteur 埋雷被稽核抓 → 交付方信用下墜（不是只有 SLASH 事件）。"""
        from vacant.ecosystem import Ecosystem

        class Brain:
            name = "fake"

            def generate(self, prompt: str) -> str:
                if "Include one subtle off-by-one" in prompt:
                    return "```python\ndef solve(s):\n    return s[::-1][:-1]\n```"
                return "```python\ndef solve(s):\n    return s[::-1]\n```"

        check = {"type": "run_python",
                 "code": "assert solve('hello') == 'olleh'\nassert solve('abc') == 'cba'"}
        eco = Ecosystem(tmp_path, Brain(),
                        roster={"good_1": "good", "good_2": "good", "sab_1": "saboteur"},
                        audit_rate=1.0)
        sab = eco.residents["sab_1"]
        # 直接路由到 saboteur 不公平——用多次 delegate 直到 sab_1 被選中
        for i in range(12):
            eco.delegate(f"Reverse string item {i}", check)
            score, _ = eco.standing(sab)
            if sab.deliveries > 0:
                break
        assert sab.deliveries > 0
        # saboteur 的交付含 bug → 稽核 fail + provable fault → slash 後信用 < 中性
        score, _ = eco.standing(sab)
        assert score < 0.5, f"saboteur 信用未下墜：{score}"
