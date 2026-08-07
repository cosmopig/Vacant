"""多向環境原語的判準（`06_多向環境架構.md` §3 的可執行版本）。

這些測試打的是**設計本身**，不是實作細節：每一條對應設計文件裡的一格。
文件改了而這裡沒改（或反過來），就是有一邊在說謊。
"""

from __future__ import annotations

import pytest

from vacant.environment import (
    CHANNELS,
    REJECTED_CHANNELS,
    CalibrationLedger,
    ChannelSpec,
    ChannelViolation,
    Declination,
    Environment,
    assert_argument_only,
    assert_channel_separation,
)


# ── 通道規格 ────────────────────────────────────────────────────────────
def test_channel_without_reason_is_refused():
    """講不出「為什麼不併進主通道」的通道不准存在——這是設計的唯一硬規定。"""
    with pytest.raises(ChannelViolation):
        ChannelSpec(name="whatever", writers=("worker",), readers=("peer",),
                    readable_phases=("OPEN",), why_not_main="   ")


def test_every_channel_answers_the_question():
    """總表裡每一條都要有理由，而且不是敷衍的一句話。"""
    for name, spec in CHANNELS.items():
        assert len(spec.why_not_main.strip()) > 20, f"{name} 的理由太短，形同沒有"


def test_rejected_channels_are_not_postable():
    """刻意不做的通道要在程式碼裡擋住，不能只寫在文件裡。"""
    env = Environment()
    for name in REJECTED_CHANNELS:
        with pytest.raises(ChannelViolation) as e:
            env.post(name, "worker", "a", "t1", {})
        assert "刻意不做" in str(e.value)


# ── 可見性 ──────────────────────────────────────────────────────────────
def test_peer_cannot_read_declination():
    """拒絕不對同儕廣播：否則『我不會』變成地位訊號，問的成本一升就沒人問。"""
    assert "peer" not in CHANNELS["declination"].readers
    env = Environment()
    env.advance("t1", "ASSIGNED")
    env.declare(Declination("a", "t1", accepted=False, reason="insufficient_context"))
    assert [p for p in env.visible("router", "t1") if p.channel == "declination"]
    assert not [p for p in env.visible("peer", "t1") if p.channel == "declination"]


def test_peer_cannot_read_reputation_before_closed():
    """評審期間不揭露信譽。這不是隱私考量是效能考量（Chen et al. 的權威壓抑）。"""
    env = Environment()
    env.advance("t1", "SEALED")
    with pytest.raises(ChannelViolation):
        env.read_reputation("peer", "t1")
    env.read_reputation("router", "t1")      # router 一直讀得到
    env.advance("t1", "CLOSED")
    env.read_reputation("peer", "t1")        # 結案後才給看


def test_review_is_invisible_until_reveal():
    """SEALED 期間評審彼此看不見——瀑布通道由建構關閉，不是靠自律。"""
    env = Environment()
    env.advance("t1", "SEALED")
    env.post("review", "peer", "r1", "t1", {"verdict": "fail"}, seal=True, nonce="n")
    assert not env.visible("peer", "t1")
    assert not [p for p in env.visible("auditor", "t1") if p.channel == "review"]
    env.advance("t1", "REVEAL")
    got = [p for p in env.visible("auditor", "t1") if p.channel == "review"]
    assert len(got) == 1 and got[0].sealed and got[0].payload == {}


def test_reveal_detects_after_the_fact_editing():
    env = Environment()
    env.advance("t1", "SEALED")
    p = env.post("review", "peer", "r1", "t1", {"verdict": "fail"}, seal=True, nonce="n")
    with pytest.raises(ChannelViolation):
        env.reveal(p, {"verdict": "pass"}, "n")
    env.reveal(p, {"verdict": "fail"}, "n")
    assert p.payload == {"verdict": "fail"}


def test_phase_cannot_go_backwards():
    """相位倒退＝把密封的東西退回可讀狀態。"""
    env = Environment()
    env.advance("t1", "REVEAL")
    with pytest.raises(ChannelViolation):
        env.advance("t1", "SEALED")


# ── 論證通道 ────────────────────────────────────────────────────────────
def test_consult_reply_may_not_carry_a_verdict():
    """Delphi 的不對稱：傳理由，不傳立場。夾帶立場就 raise（不要繞過）。

    誠實邊界：詞表擋得住直白的夾帶，擋不住改寫過的（與 KS-1 的詞表同一種
    限制）。**真正承重的是結構**——回覆沒有分數欄位，而且諮詢過的人不得
    評審同一件（下一條測試）。詞表是防呆，不是過濾器。
    """
    assert_argument_only("邊界條件通常出在空輸入與極大值兩端")
    for bad in ("這個看起來 pass", "我覺得這個沒問題", "給 8 分"):
        with pytest.raises(ChannelViolation):
            assert_argument_only(bad)


def test_consulted_agent_may_not_review_the_same_task():
    """結構性反串供：看過草稿的人不得評審同一件。

    為什麼要結構性而不是統計偵測：Anderson & Holt 指出相關性不需要共謀就會
    出現，所以事後統計會誤傷只是「評審順序較後」的誠實 agent。
    """
    env = Environment()
    env.consult("w", "h2", "t1", "邊界怎麼看", "空輸入與極大值兩端要先列成條款")
    assert_channel_separation(env, "t1", ("h1", "h3", "h4"))
    with pytest.raises(ChannelViolation):
        assert_channel_separation(env, "t1", ("h1", "h2", "h3"))


def test_human_flag_carries_no_verdict():
    """人類介入只帶注意力，不帶判決——展場第 3 拍能成立的原因。"""
    env = Environment()
    p = env.flag("visitor", "t1", note="這個看起來怪")
    assert p.payload["verb"] == "FLAG"
    assert not any(k in p.payload for k in ("verdict", "score", "correct", "pass"))


def test_only_human_writes_intervention():
    env = Environment()
    with pytest.raises(ChannelViolation):
        env.post("intervention", "worker", "a", "t1", {"verb": "HALT"})


# ── calibration 帳 ─────────────────────────────────────────────────────
def test_decline_reason_must_be_a_structural_code():
    """管轄權主張會用系統獎勵的術語提出（Abbott）——給自由文字等於邀請發明理由。"""
    with pytest.raises(ValueError):
        Declination("a", "t1", accepted=False, reason="我今天不想做")


def test_naive_calibration_is_gamed_by_over_declining():
    """規格書的計分法可以被「多拒一點」刷分，Youden's J 不行。

    代數上就看得出來：naive ＝ [#(拒∧會失敗) − #(接∧失敗)] / N，
    **完全不含「拒了一件本來會成功的」那一格**。所以拒絕率越高分數越高，
    上限在 P(會失敗) 拿滿。J ＝ P(拒|會失敗) − P(拒|會成功) 則兩格都算，
    全拒 ⇒ J = 1 − 1 = 0。

    這就是為什麼 `06 §5.1` 說 calibration 維必須是**判別力**不是計數。
    但注意下一條：J 也不是萬能的——它擋得住「亂拒」，擋不住「挑簡單任務」
    （挑食者的拒絕確實與它自己的失敗相關），那要靠 coverage。
    """
    always, sharp, orth = CalibrationLedger(), CalibrationLedger(), CalibrationLedger()
    for i in range(400):
        would_fail = (i % 2 == 0)
        always.record("all_decline", False, would_fail)          # 全拒
        sharp.record("sharp", not would_fail, would_fail)        # 完美判別
        orth.record("noise", (i // 2) % 2 == 0, would_fail)      # 與真值正交

    assert always.naive_score("all_decline") == 0.5, "全拒把計數版刷到滿分"
    assert always.discrimination("all_decline") == 0.0, "而 J 誠實地給 0"
    assert always.coverage("all_decline") == 0.0

    assert sharp.discrimination("sharp") == 1.0
    assert abs(orth.discrimination("noise")) < 0.06


def test_calibration_refuses_degenerate_endpoints():
    """一邊沒有樣本就不給數字——不要在退化端點上量效應量。"""
    led = CalibrationLedger()
    for _ in range(20):
        led.record("a", True, False)
    assert led.discrimination("a") is None
    assert led.coverage("a") == 1.0
