"""通道分離兩格的迴歸判準（2026-08-07）。

來源：`參考文獻/2026-08-06_人類運作邏輯/HUMAN_MECHANISMS.md` §0／§6.2／§6.5。
每一支都對應一個「若退回去就會讓結論不成立」的性質：

  1. **既有數字不准被擾動**。key 加一維會改變 cell 位置與線材格式，而
     `entrycost.SimConfig.digest()` 同時是亂數種子——上一輪就是這樣把 E1–E16
     無聲位移過。所以：三參數呼叫必須落在同一格、序列化在 family=="" 時仍寫
     三段 key、既有 review 簽章逐位仍驗得過。
  2. 坑型由**交付時觀察**決定，reviewer 不得自選要落在哪一格（否則「專長」
     這條通道退化成可自報的標籤）。
  3. 見習判定與 weight 內生仍是**身份層級**的：換一個沒做過的坑型不該讓已證明
     的身份重新被當新人。
  4. 密封面板的三道檢查（未承諾不得揭露、面板未關不得揭露、揭露須雜湊得回承諾），
     以及「面板開啟中 `visible_votes` 回空」——瀑布由建構關閉的那一行。
  5. 分族路由的兩個判準要**同時**成立：專家命中率上升 **且** 品質不變差。
     只驗前者的話，一個只會挑簡單題的路由器也會過關。
  6. 虛無對照：沒有真專長時，分族不得帶來品質增益。
  7. `_behavior_same_source` 的鑑別題過濾是**承重的**：拿掉它，未密封面板會把
     互不相干的評審判成同源。這條過濾本來是為了別的理由加的，別順手簡化掉。
"""
from __future__ import annotations

import pytest

from vacant import crypto
from vacant.body import CapabilityCard
from vacant.channels import (
    SealConfig, SpecConfig, simulate_seal, simulate_specialty,
)
from vacant.envelope import ReviewEnvelope
from vacant.identity import Identity, PublicIdentity
from vacant.logbook import Logbook, review_commitment
from vacant.registry import Registry, ReviewRejected
from vacant.reputation import DIMS, Reputation


# ── 1. 相容性：後加的維度維持預設時，不准改變任何既有位元 ──────────────
class TestBackwardCompatible:
    def test_three_arg_calls_land_in_the_same_cell(self):
        """三參數呼叫（既有全部呼叫端）＝ family "" 那一格。"""
        rep = Reputation()
        rep.record_review("s1", "main", "echo", {d: 1.0 for d in DIMS})
        assert set(rep._cells) == {("s1", "main", "echo", "")}
        assert rep.score("s1", "main", "echo") == rep.score("s1", "main", "echo", "")

    def test_wire_format_unchanged_when_family_default(self):
        """family=="" 時序列化仍寫**三段** key —— 既有 state 檔逐位不變。

        `tests/test_credit_memory.py` 釘死了 {"s1␟main␟echo", ...}；那支若因為
        本改動而失敗，代表所有 registry_state.json 都要重生。"""
        rep = Reputation()
        rep.record_review("s1", "main", "echo", {d: 1.0 for d in DIMS})
        assert set(rep.to_json()["cells"]) == {"s1␟main␟echo"}
        rep.record_review("s1", "main", "echo", {d: 1.0 for d in DIMS}, family="boundary")
        assert set(rep.to_json()["cells"]) == {"s1␟main␟echo", "s1␟main␟echo␟boundary"}

    def test_old_three_part_keys_still_load(self):
        rep = Reputation.from_json({"s1␟main␟echo": {d: [3.0, 1.0, 0] for d in DIMS}})
        assert ("s1", "main", "echo", "") in rep._cells
        assert rep.score("s1", "main", "echo") == pytest.approx(0.75)

    def test_existing_review_signature_still_verifies(self):
        """family 維持預設時不進簽章核心 → 已歸檔的 review 簽章仍驗得過。"""
        ident = Identity.generate()
        env = ReviewEnvelope.create(
            ident, target_id="t", target_stream_id="s", branch_id="main",
            target_head="h", task_id="k", substrate="echo",
            scores={d: 1.0 for d in DIMS}, ts_ms=1)
        pub = PublicIdentity(ident.vacant_id, ident.pub)
        assert "family" not in env._core()
        assert "family" not in env.to_json()
        assert env.verify_sig(pub)
        env2 = ReviewEnvelope.create(
            ident, target_id="t", target_stream_id="s", branch_id="main",
            target_head="h", task_id="k", substrate="echo",
            scores={d: 1.0 for d in DIMS}, ts_ms=1, family="boundary")
        assert env2.sig != env.sig          # 非預設時進核心 → 被簽章覆蓋
        assert env2.verify_sig(pub)
        assert ReviewEnvelope.from_json(env.to_json()).family == ""


# ── 2/3. 坑型是交付端宣告的，不是 reviewer 自選的 ───────────────────────
def _pair() -> tuple[Registry, Identity, Identity, Logbook]:
    reg = Registry()
    tgt, rev = Identity.generate(), Identity.generate()
    book = Logbook()
    book.append("GENESIS", {"w": "t"}, tgt, ts_ms=0)
    for who, ident in (("t", tgt), ("r", rev)):
        reg.announce(CapabilityCard(
            vacant_id=ident.vacant_id, niches=["code"],
            pub_hex=crypto.pub_to_hex(ident.pub), controller=who))
    return reg, tgt, rev, book


class TestFamilyIsObserved:
    def test_reviewer_cannot_invent_a_family(self):
        reg, tgt, rev, book = _pair()
        head = book.append("D", {}, tgt, ts_ms=1).hash()
        reg.note_head(tgt.vacant_id, book.stream_id(), "main", head,
                      substrate="echo", family="boundary")
        env = ReviewEnvelope.create(
            rev, target_id=tgt.vacant_id, target_stream_id=book.stream_id(),
            branch_id="main", target_head=head, task_id="k", substrate="echo",
            scores={d: 1.0 for d in DIMS}, ts_ms=1, family="off_by_one")
        with pytest.raises(ReviewRejected, match="family"):
            reg.record_review(env)

    def test_unlabelled_delivery_is_the_general_channel_not_a_free_slot(self):
        """未宣告坑型 ⇒ 只能寫進 ""，不是「隨便挑一格」。"""
        reg, tgt, rev, book = _pair()
        head = book.append("D", {}, tgt, ts_ms=1).hash()
        reg.note_head(tgt.vacant_id, book.stream_id(), "main", head, substrate="echo")
        env = ReviewEnvelope.create(
            rev, target_id=tgt.vacant_id, target_stream_id=book.stream_id(),
            branch_id="main", target_head=head, task_id="k", substrate="echo",
            scores={d: 1.0 for d in DIMS}, ts_ms=1, family="boundary")
        with pytest.raises(ReviewRejected, match="family"):
            reg.record_review(env)

    def test_standing_aggregates_across_families(self):
        """身份層級的問題（weight／見習／未證明降權）跨族聚合，不因換族歸零。"""
        reg, tgt, rev, book = _pair()
        for i, fam in enumerate(("boundary", "off_by_one", "empty_input")):
            head = book.append("D", {"i": i}, tgt, ts_ms=i + 1).hash()
            reg.note_head(tgt.vacant_id, book.stream_id(), "main", head,
                          substrate="echo", family=fam)
            reg.record_review(ReviewEnvelope.create(
                rev, target_id=tgt.vacant_id, target_stream_id=book.stream_id(),
                branch_id="main", target_head=head, task_id=f"k{i}", substrate="echo",
                scores={d: 1.0 for d in DIMS}, ts_ms=1, family=fam))
        _s_all, obs_all = reg.standing(tgt.vacant_id, "echo")
        _s_one, obs_one = reg.standing(tgt.vacant_id, "echo", family="boundary")
        assert obs_all > obs_one > 0        # 聚合看得到三族，單族只看一族
        assert reg._score_obs(tgt.vacant_id, "echo")[1] == pytest.approx(obs_all)

    def test_slash_hits_every_family(self):
        """provable fault 是身份層級的事實：不准只扣被派到的那一族。"""
        reg, tgt, rev, book = _pair()
        for i, fam in enumerate(("boundary", "off_by_one")):
            head = book.append("D", {"i": i}, tgt, ts_ms=i + 1).hash()
            reg.note_head(tgt.vacant_id, book.stream_id(), "main", head,
                          substrate="echo", family=fam)
            reg.record_review(ReviewEnvelope.create(
                rev, target_id=tgt.vacant_id, target_stream_id=book.stream_id(),
                branch_id="main", target_head=head, task_id=f"k{i}", substrate="echo",
                scores={d: 1.0 for d in DIMS}, ts_ms=1, family=fam))
        before = {f: reg.reputation_of(tgt.vacant_id, "echo", f)
                  for f in ("boundary", "off_by_one")}
        assert reg.apply_slash(tgt.vacant_id, "echo", 0.5)
        for f, b in before.items():
            assert reg.reputation_of(tgt.vacant_id, "echo", f) < b, f"{f} 沒被扣到"


# ── 4. 密封面板 ───────────────────────────────────────────────────────
class TestSealedPanel:
    def _sealed(self):
        reg, tgt, rev, book = _pair()
        reg.sealed_reviews = True
        head = book.append("D", {}, tgt, ts_ms=1).hash()
        reg.note_head(tgt.vacant_id, book.stream_id(), "main", head, substrate="echo")
        env = ReviewEnvelope.create(
            rev, target_id=tgt.vacant_id, target_stream_id=book.stream_id(),
            branch_id="main", target_head=head, task_id="k", substrate="echo",
            scores={d: 1.0 for d in DIMS}, ts_ms=1)
        return reg, env

    def test_open_panel_hides_votes(self):
        """瀑布通道由建構關閉：面板開啟中，前面的人怎麼投在資訊上不存在。"""
        reg, env = self._sealed()
        reg.open_panel("k")
        assert reg.visible_votes("k") == {}
        nonce = "n" * 32
        reg.commit_review(env.reviewer_id, "k", review_commitment(env.to_json(), nonce))
        assert reg.visible_votes("k") == {}      # 承諾在鏈上、內容不在
        reg.close_panel("k")
        reg.record_review(env, nonce=nonce)
        assert reg.visible_votes("k") == {env.reviewer_id: True}

    def test_reveal_without_commit_rejected(self):
        reg, env = self._sealed()
        reg.open_panel("k")
        reg.close_panel("k")
        with pytest.raises(ReviewRejected, match="未承諾"):
            reg.record_review(env, nonce="n" * 32)

    def test_reveal_before_close_rejected(self):
        reg, env = self._sealed()
        reg.open_panel("k")
        nonce = "n" * 32
        reg.commit_review(env.reviewer_id, "k", review_commitment(env.to_json(), nonce))
        with pytest.raises(ReviewRejected, match="尚未關閉"):
            reg.record_review(env, nonce=nonce)

    def test_reveal_mismatch_rejected(self):
        reg, env = self._sealed()
        reg.open_panel("k")
        reg.commit_review(env.reviewer_id, "k",
                          review_commitment(env.to_json(), "n" * 32))
        reg.close_panel("k")
        with pytest.raises(ReviewRejected, match="不符"):
            reg.record_review(env, nonce="m" * 32)   # 換 nonce＝換了承諾的內容

    def test_cannot_change_commitment(self):
        reg, env = self._sealed()
        reg.open_panel("k")
        reg.commit_review(env.reviewer_id, "k", "a" * 64)
        with pytest.raises(ReviewRejected, match="重複承諾"):
            reg.commit_review(env.reviewer_id, "k", "b" * 64)

    def test_short_nonce_refused(self):
        """hiding 全靠 nonce 的熵：評語空間小到可以窮舉，短 nonce 等於沒密封。"""
        with pytest.raises(ValueError, match="nonce"):
            review_commitment({"a": 1}, "short")

    def test_sealed_off_is_bit_identical_path(self):
        """sealed_reviews=False → 完全不碰面板，既有行為原封不動。"""
        reg, env = self._sealed()
        reg.sealed_reviews = False
        assert reg.record_review(env) > 0

    def test_state_survives_restart(self):
        """坑型宣告與面板承諾必須跨行程續存。

        不續存 ⇒ 重啟就能「換一族改掛」或「丟掉承諾後重投」，兩道檢查同時被繞過。
        既有的 `unproven_rank` / `route_seq` 是為同一個理由續存的（獨立審查 P1-3）。"""
        import json as _json
        reg, env = self._sealed()
        reg.open_panel("k")
        nonce = "n" * 32
        commit = review_commitment(env.to_json(), nonce)
        reg.commit_review(env.reviewer_id, "k", commit)
        reg2 = Registry()
        reg2.state_from_json(_json.loads(_json.dumps(reg.state_to_json())))
        assert reg2.sealed_reviews is True
        assert reg2.panel_open("k") and reg2.visible_votes("k") == {}
        with pytest.raises(ReviewRejected, match="重複承諾"):
            reg2.commit_review(env.reviewer_id, "k", "b" * 64)

    def test_unused_channel_features_leave_state_bit_identical(self):
        """沒用到通道分離的部署，state 檔不得多出任何鍵。"""
        st = Registry().state_to_json()
        assert not ({"head_family", "panel_commit", "panel_closed", "sealed_reviews"}
                    & set(st))


# ── 5/6. 專長 profile 的兩個判準 ────────────────────────────────────────
class TestSpecialtyRouting:
    ROUNDS = 300

    def _run(self, **kw):
        return simulate_specialty(SpecConfig(rounds=self.ROUNDS, seed="t-spec", **kw))

    def test_expert_rate_up_and_quality_not_worse(self):
        """**兩個都要驗**：只驗專家命中率的話，只挑簡單題的路由器也會過關。

        任務流是外生的（坑型只由 seed 與輪次決定），所以兩臂的每族題數必須
        逐位相同——這是「品質沒有被挑題挑出來」的直接證據。"""
        off = self._run(profile_on=False)
        on = self._run(profile_on=True)
        assert off["per_family_tasks"] == on["per_family_tasks"], "任務流不是外生的"
        assert off["budget_exact"] and on["budget_exact"]        # == 不是 <=
        assert off["deliveries"] == on["deliveries"] == self.ROUNDS
        # ①專家命中率：不分族臂 ≈ 隨機（1/6）；分族臂顯著高於它
        assert off["expert_rate"] < 2 * off["chance_rate"]
        assert on["expert_rate"] > off["expert_rate"] + 0.15
        # ②總交付品質不得變差
        assert on["quality"] >= off["quality"]

    def test_null_control_no_gain_without_real_specialisation(self):
        """沒有真專長時分族不得帶來增益——否則量到的是「換了個參數」。"""
        off = self._run(profile_on=False, specialists=False)
        on = self._run(profile_on=True, specialists=False)
        assert off["expert_rate"] is None and on["expert_rate"] is None
        assert abs(on["quality"] - off["quality"]) < 0.01

    def test_evidence_is_split_not_created(self):
        """誠實邊界的可執行版：分族只是把同一批證據切細，總量不變。"""
        off = self._run(profile_on=False)
        on = self._run(profile_on=True)
        assert on["n_cells"] > off["n_cells"]
        assert on["obs_per_cell_mean"] < off["obs_per_cell_mean"]


# ── 7. commit-reveal：殘餘相關性與偵測器的推論地位 ────────────────────
class TestSealCorrelation:
    ROUNDS = 150

    def _run(self, **kw):
        return simulate_seal(SealConfig(rounds=self.ROUNDS, seed="t-seal", **kw))

    def test_sealed_arm_is_invariant_to_herding(self):
        """密封臂對 herd 參數**完全**不敏感 → 瀑布是由建構關閉的。

        這是本格最強的一條：不是「效果變小」，是「那條通道不存在」。"""
        base = self._run(sealed=True, herd=0.0)
        for h in (0.3, 0.6, 0.9, 1.0):
            r = self._run(sealed=True, herd=h)
            assert r["agree_indep_indep"] == base["agree_indep_indep"]
            assert r["herd_overrides"] == 0

    def test_open_panel_manufactures_correlation_with_zero_same_source(self):
        """n_clones=0：沒有任何同源通道，相關性只能是架構造成的。"""
        op = self._run(sealed=False, n_clones=0, herd=0.6)
        se = self._run(sealed=True, n_clones=0, herd=0.6)
        assert op["agree_indep_indep"] > se["agree_indep_indep"]
        assert op["agree_indep_indep_raw"] > se["agree_indep_indep_raw"]
        assert op["herd_overrides"] > 0 and se["herd_overrides"] == 0

    def test_cascade_masks_real_same_source(self):
        """反方向也要報：瀑布不只製造假相關，它還**蓋掉真的同源**。

        克隆共用同一份私訊號 ⇒ 密封時一致率 1.0、必被偵測；未密封時他們在不同
        位置各自跟隨多數而分歧，一致率掉到門檻以下，承重偵測器一個都抓不到。"""
        op = self._run(sealed=False, n_clones=2, herd=0.6)
        se = self._run(sealed=True, n_clones=2, herd=0.6)
        assert se["agree_clone_clone"] == 1.0
        assert op["agree_clone_clone"] < se["agree_clone_clone"]
        assert se["true_positives"] == 2
        assert op["true_positives"] < se["true_positives"]

    def test_informative_filter_is_load_bearing(self):
        """`_behavior_same_source` 的鑑別題過濾不是裝飾：拿掉它，未密封面板
        會把互不相干的評審判成同源（原始一致率越過 0.9 門檻）。"""
        op = self._run(sealed=False, n_clones=0, herd=0.9)
        se = self._run(sealed=True, n_clones=0, herd=0.9)
        assert op["raw_would_flag_indep"] is True
        assert se["raw_would_flag_indep"] is False
        assert op["false_positives"] == 0   # 有過濾 → 實際上沒有誤報

    def test_degenerate_endpoint_reports_none_not_a_number(self):
        """herd=1.0：全票一致、鑑別題歸零。退化端點必須回 None，不准回一個數字
        （`_index/methods.json` 分析紀律第 2 條）。"""
        r = self._run(sealed=False, herd=1.0)
        assert r["n_informative"] == 0
        assert r["agree_indep_indep"] is None
        assert r["unanimous_rate"] == 1.0
