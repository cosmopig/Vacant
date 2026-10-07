"""P13 第四輪：命盤卡第 2–4 行「殘句不上卡」＋前綴三端一致＋現實詞不上卡（負控制／正控制都釘住）。

* 殘句判斷是結構規則（`fortune.frag_reason`），不只字表：負控制 25 句（第三輪真跑上過卡的 5 句＋造的 20 句）一律要被擋，
  正控制 20 句完整句一律要放行——兩邊都測，量具才算會動。
* 前綴：第 2 行「它心裡想：」、第 3 行「它試了：」（永遠，不再有「它試了，現在…」）、第 4 行「試完它說：」；
  手機 `fortuneViewOf/splitPrefix`（≤12 字、不含標點）與電視 `drawFortuneCardLines`（2–14 字＋冒號）都認得。
"""
from __future__ import annotations

import json
import pathlib
import re

import pytest

from ops.exhibit.twin import fortune as fz

F = {"mbti": "ENFP", "zodiac": "雙子", "blood": "AB"}
ROOT = pathlib.Path(__file__).resolve().parents[1]
R4 = ROOT / "ops/exhibit/twin/evidence_divine_20261007/round4"

# 第三輪真跑上過卡（或掉到標題）的殘句
REAL_FRAGMENTS = [
    "讓那封信裡沉重的、沒說出口的情感",                         # a12 第 2 行
    "雖然沒有聽到預想中的旋律，但這種構造被撥動後的反應",      # a2 第 4 行
    "他想面對債務，而我給他的這個動作",                         # a7 第 4 行
    "雖然種子還沒動彈，但看到那些邏輯線條與這艘靜止的船結合在一起",   # a8 第 4 行
    "點數單對齊紀錄",                                            # a6 第 3 行（退到標題）
]
MADE_FRAGMENTS = [
    "把那張紙放在", "他把信放進了長椅上的", "在長桌廣場的土堆上", "那顆帶著三道溝槽的陶杯", "雖然它沒有真的漂起來",
    "因為那塊土太乾了", "如果把線繫在洞口上", "當我把紙遞進去的時候", "並且在旁邊畫了一圈對稱的線條",
    "是讓那些被遺忘的聲音有了一個地方", "讓盒子裡那根斷掉的齒", "那個在暗處等了很久的", "裡面有一顆被土蓋住一半的",
    "他在長椅旁邊看見的那個", "紙船的位置稍微偏移了一點之後", "然後把它", "那種緊繃的感覺", "還有那條被風吹起來的細線",
    "它似乎需要一個更穩定的", "裡面的轉軸卡住了或者",
    "我感覺到那種發燙的東西被轉化成了一點點聲音，雖然很小聲",    # 句尾掛著「雖然…」
    "在草稿角那面刻有高低線的石壁上",                              # 只交代地點
]
COMPLETE = [
    "讓長桌廣場的桌五音樂盒發出聲音", "讓碗口缺了三角的陶碗重新完整", "把長椅上的紙筒拿走了，現在長椅中間是空的",
    "雖然沒辦法真的把那些話說出來，但至少它們現在有一個可以被握住的樣子",
    "這塊土雖然沉重，但它終於不再是那個被所有人繞開的邊緣了",
    "我把沒人認領的第六封信用細線繫在了右邊長椅下的灰藍小東西上", "紙船斜靠在洞口，裝著一顆種子",
    "音樂盒現在能完整地響到最後一個音了", "那個斷掉的字現在完整了", "它把補片塞進了碗口的缺口裡",
    "我在石壁上壓了一個灰藍色的指尖印紋", "線穿過了兩張信紙的孔",
    "土堆上多了一艘帶著赭紅底座的紙船", "當數字與實物終於在空間裡對齊時，那種緊繃的感覺才稍微鬆開了一點",
    "它終於有了正確的位置", "盒子發出了「咚」一聲", "郵筒下多出一條打了結的細線", "長椅中間現在放著這個帶有沙金質感的紙團",
    "種子還沒動彈，但紙船已經停在洞口了", "它把信紙折成了一隻小船，放在長椅上", "把音樂盒挪到了兩道光交界的地",
]


def test_negative_controls_every_fragment_is_caught_strict_and_the_gauge_is_not_all_reject() -> None:
    assert len(REAL_FRAGMENTS) + len(MADE_FRAGMENTS) >= 25
    for s in REAL_FRAGMENTS + MADE_FRAGMENTS:
        assert fz.frag_reason(s, terminated=False) is not None, s
        if s.startswith("讓"):                                         # 願望句（讓…）另用 wish=True 的規則也要擋
            assert fz.frag_reason(s, terminated=False, wish=True) is not None, s


def test_positive_controls_complete_sentences_pass_both_strict_and_terminated() -> None:
    assert len(COMPLETE) >= 20
    for s in COMPLETE:
        w = s.startswith("讓")                                          # 「讓…」是願望的寫法；非願望的句子不以「讓」開頭（接續詞）
        assert fz.frag_reason(s, terminated=False, wish=w) is None, (s, fz.frag_reason(s, terminated=False, wish=w))
        assert fz.frag_reason(s, terminated=True) is None, s


def test_wishes_that_start_with_a_verb_are_not_nominal_fragments() -> None:
    for s in ("看哨子的裂縫能不能再響一次", "聽見音樂盒的第十二個音", "弄清楚一個能容納所有訴說的容器", "讓音樂盒斷掉的那個音，有東西接住"):
        assert fz.frag_reason(s, terminated=False, wish=True) is None, s


def test_real_run_fragments_never_reach_the_card_through_the_composers() -> None:
    # a12：「讓…的情感，變成…」太長就取完整句；整句不超過上限就整句，不在「，」切出沒有謂語的前半
    w = fz.wish_of("我想：讓那封信裡沉重的、沒說出口的情感，變成一個能被遞交到雙手中的實體物件。\n", "x", F)
    assert w and w.endswith("實體物件"), w
    long_ = "我想：讓那封信裡沉重的、沒說出口的情感，" + "變成一個能被遞交到雙手中而且不會被任何人拆開的實體物件" * 2 + "。\n"
    assert fz.wish_of(long_, "x", F) is None, "整句超過上限、前半是殘句 ⇒ 寧缺"
    # a2：整句 49 字、≤ 上限 ⇒ 整句（模型自己寫完的完整句）
    s = fz.said_of("感想：雖然沒有聽到預想中的旋律，但這種構造被撥動後的反應，讓這個盒子從靜止的物件變成了有反應的結構。\n", "x", F)
    assert s == "雖然沒有聽到預想中的旋律，但這種構造被撥動後的反應，讓這個盒子從靜止的物件變成了有反應的結構"
    # 超過上限且前半是殘句 ⇒ 寧缺（不是印出「…被撥動後的反應」）
    long_said = "感想：雖然沒有聽到預想中的旋律，但這種構造被撥動後的反應" + "，讓這個盒子從靜止的物件變成了有反應的結構而且它還在輕輕地震動著並且不肯停下來" + "。\n"
    assert fz.said_of(long_said, "x", F) is None
    # a8：「但看到…結合在一起」是時間殘片
    s8 = "感想：雖然種子還沒動彈，但看到那些邏輯線條與這艘靜止的船結合在一起，我感覺到了一種被守護的脈動。\n"
    assert fz.said_of(s8, "x", F).endswith("被守護的脈動")
    assert fz.said_of("感想：雖然種子還沒動彈，但看到那些邏輯線條與這艘靜止的船結合在一起，而且" + "很久" * 20 + "。\n", "x", F) is None
    # a6：改變段太長、前半完整 ⇒ 取完整子句；沒有改變段、只有標題 ⇒ 沒有這一行（標題不當候選）
    t = fz.tried_of("點數單對齊紀錄\n\n感想：好。\n", "x", F)
    assert t is None
    assert fz.tried_of("修補陶哨子的裂縫\n", "x", F) is None
    # 掛著的句子換下一個候選：改變段第一句是殘句、第二句完整
    rec = "標題\n\n改變：在石壁上的。紙船現在斜靠在洞口。\n感想：好。\n"
    assert fz.tried_of(rec, "x", F) == "它試了：紙船現在斜靠在洞口"


def test_prefix_of_line_three_is_always_it_tried_colon() -> None:
    # 第三輪 a8／a12：「它試了，現在…」——前綴被句子吃掉，手機與電視拆前綴會失敗
    rec = "標題\n\n改變：現在小燈亮著。\n感想：好。"
    assert fz.tried_of(rec, "x", F) == "它試了：現在小燈亮著"
    long_ = "改變：" + "原本兩道光交界的地是一片平整而且沒有任何標記的青灰綠色區域所以什麼都沒有發生過也沒有人來過這個地方留下任何腳印，現在那個點出現了一圈細線\n感想：好。"
    assert fz.tried_of("標題\n" + long_, "x", F) == "它試了：現在那個點出現了一圈細線"
    for lines_src in ((R4 / "cards_offline.json"),):
        if not lines_src.exists():
            pytest.skip("round4 離線重組檔不在")
        for r in json.loads(lines_src.read_text(encoding="utf-8")):
            for ln in r["lines"][1:]:
                assert ln.startswith((fz.WANT_PREFIX, fz.TRIED_PREFIX, fz.SAID_PREFIX)), ln
                assert not ln.startswith("它試了，")


def test_prefix_set_is_pinned_and_both_client_splitters_accept_every_prefix() -> None:
    assert (fz.VERDICT_PREFIX, fz.WANT_PREFIX, fz.TRIED_PREFIX, fz.SAID_PREFIX) == \
        ("你的數位分身其實是：", "它心裡想：", "它試了：", "試完它說：")
    # 手機 index.html splitPrefix：/^([^：:，,。；;！!？?\s「」（）()]{1,12})[：:]\s*([\s\S]+)$/
    phone = re.compile(r"^([^：:，,。；;！!？?\s「」（）()]{1,12})[：:]\s*([\s\S]+)$")
    # 電視 world3 drawFortuneCardLines split：/^([^：:]{2,14}[：:])(.+)$/
    tv = re.compile(r"^([^：:]{2,14}[：:])(.+)$")
    body = "把補片塞進了碗口的缺口裡，讓那個陶碗變成了完整的樣子"
    for pre in (fz.WANT_PREFIX, fz.TRIED_PREFIX, fz.SAID_PREFIX):
        assert phone.match(pre + body).group(1) + "：" == pre
        assert tv.match(pre + body).group(1) == pre
    # 「它試了，現在…」這種前綴被吃掉的寫法兩端都拆不出前綴（第三輪的毛病）
    assert phone.match("它試了，現在它斜靠在洞口").group(1) if phone.match("它試了，現在它斜靠在洞口") else True
    assert not phone.match("它試了，現在它斜靠在洞口處")
    # 客戶端真的有這兩條規則（兩個 repo 不在本機就略過那一半）
    cloud = pathlib.Path("/Users/cosmopig/Documents/GitHub/vacant-world-cloud-wt-p13/public/index.html")
    if cloud.exists():
        assert r"[^：:，,。；;！!？?\s「」（）()]{1,12}" in cloud.read_text(encoding="utf-8")
    tvf = pathlib.Path("/Users/cosmopig/Documents/GitHub/vacant_hm-wt-p13/world3/index.html")
    if tvf.exists():
        assert r"/^([^：:]{2,14}[：:])(.+)$/" in tvf.read_text(encoding="utf-8")


def test_reality_words_never_reach_lines_two_three_four() -> None:
    for w in ("債務", "欠款", "貸款", "工作", "考試", "論文", "老闆", "前任", "薪水", "房租"):
        assert fz.mentions_reality(f"他想面對{w}的事"), w
    said = "感想：他想面對債務，而我給他的這個動作，是讓那些被遺忘的聲音與那個在呼吸的生命產生連結。\n"
    assert fz.said_of(said, "x", F) is None
    # 感想的前半不含現實詞也一樣不能因為切到別的子句就帶進來：含債務的整句、含債務的前綴都被擋
    assert fz.said_of("感想：我終於還清了欠款，那些被遺忘的聲音現在有了一個地方可以待著。\n", "x", F) is None
    assert fz.tried_of("t\n\n改變：我把貸款單放在長椅上。\n感想：好。\n", "x", F) is None
    assert fz.wish_of("我想：讓老闆留下的那張紙變成一艘船。\n", "x", F) is None
    # 負控制的負控制：沒有現實詞的照常上卡
    assert fz.said_of("感想：那些被遺忘的聲音現在有了一個地方可以待著。\n", "x", F) == "那些被遺忘的聲音現在有了一個地方可以待著"


def test_offline_recompute_of_24_runs_has_no_fragment_and_line_two_rate() -> None:
    p = R4 / "cards_offline.json"
    if not p.exists():
        pytest.skip("round4 離線重組檔不在")
    rows = json.loads(p.read_text(encoding="utf-8"))
    assert len(rows) == 24
    for r in rows:
        for ln in r["lines"][1:]:
            body = ln.split("：", 1)[1]
            assert fz.frag_reason(body, terminated=True) is None, ln
            assert not fz.mentions_reality(body), ln
            assert len(ln) <= 60, ln
    a = [r for r in rows if r["id"].startswith("a")]
    v = [r for r in rows if r["id"].startswith("v")]
    assert sum(any(x.startswith(fz.WANT_PREFIX) for x in r["lines"]) for r in a) >= 10
    assert sum(any(x.startswith(fz.WANT_PREFIX) for x in r["lines"]) for r in v) >= 10
