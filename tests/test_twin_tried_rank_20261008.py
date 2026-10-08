"""P13 第五輪：卡第 3 行要和第 2 行有關——候選排序優先選與願望共用關鍵名詞的完整句（正負控制）。"""
from __future__ import annotations

from ops.exhibit.twin import fortune as fz

F = {"mbti": "ENFP", "zodiac": "雙子", "blood": "AB"}
WISH = "讓那張被土蓋住一半、帶有三角形缺口的紙卡重新回到它該在的位置"

# 端到端實跑的樣子：改變段第一句是旁枝（筆芯），紙卡在後面（改變段第二句）
REC_CHANGE2 = ("試的紀錄.md\n\n修補紙卡\n\n我先去土堆翻了翻。\n\n"
               "改變：我把長桌廣場舊東西堆裡的一個筆芯斷截拿走了。我把那張紙卡放回了格狀圖的空位，現在紙卡缺口朝上。\n\n感想：好。\n")
# 紙卡只出現在正文、改變段沒提
REC_BODY = ("試的紀錄.md\n\n修補紙卡\n\n我撥開土，把那張紙卡放回了格狀圖的空位。\n\n"
            "改變：我把長桌廣場舊東西堆裡的一個筆芯斷截拿走了。\n\n感想：好。\n")
REC_NONE = "試的紀錄.md\n\n整理\n\n我去土堆翻了翻。\n\n改變：我把長桌廣場舊東西堆裡的一個筆芯斷截拿走了。\n\n感想：好。\n"


def test_shared_noun_in_change_para_wins_over_side_branch():
    t = fz.tried_of(REC_CHANGE2, "x", F, WISH)
    assert t and "紙卡" in t and "筆芯" not in t


def test_shared_noun_in_body_beats_unrelated_change_sentence():
    t = fz.tried_of(REC_BODY, "x", F, WISH)
    assert t and "紙卡" in t and "放回" in t


def test_no_overlap_falls_back_to_current_order():
    assert fz.tried_of(REC_NONE, "x", F, WISH) == fz.tried_of(REC_NONE, "x", F) == "它試了：把長桌廣場舊東西堆裡的一個筆芯斷截拿走了"


def test_no_wish_equals_old_behavior():
    assert fz.tried_of(REC_CHANGE2, "x", F) == fz.tried_of(REC_CHANGE2, "x", F, None)
    assert "筆芯" in fz.tried_of(REC_CHANGE2, "x", F)


def test_negative_control_unrelated_wish_does_not_pull_in_sentence():
    # 願望講的是別的東西 ⇒ 不因為「共用」而換句
    assert fz.tried_of(REC_BODY, "x", F, "讓遠處的鐘聲響起來") == "它試了：把長桌廣場舊東西堆裡的一個筆芯斷截拿走了"


def test_generic_and_abstract_bigrams_do_not_count():
    assert fz.shared_with_wish("沉重的位置", "讓沉重的東西回到位置") == 0
    assert fz.shared_with_wish("放回紙卡", WISH) >= 1


def test_every_char_from_record_and_compose_wires_wish():
    t = fz.tried_of(REC_CHANGE2, "x", F, WISH)
    body = t[len(fz.TRIED_PREFIX):].replace("它", "我")
    assert all(ch in REC_CHANGE2 or ch in "它我" for ch in body)
    res = fz.compose_card_v3(F, plan_text=f"我想：{WISH}。\n", record_text=REC_CHANGE2, rows=[], files={}, retries=0)
    assert res["tried_line"] and "紙卡" in res["tried_line"]


def test_result_sentence_in_change_is_not_displaced_by_body_action():
    """主線 2026-10-08：改變段第一句已是結果句（現在…）時，正文的動作句不插隊（round5 盲評 v1：評審偏好結果句）。"""
    rec = ("我先走到長桌廣場。我把陶哨子塞進了桌五上那個音樂盒裡斷掉的第 12 個音的位置。\n\n"
           "改變：長桌廣場桌五上的音樂盒現在能完整地響到最後一個音了。\n\n感想：聲音回來了。")
    t = fz.tried_of(rec, "x", F, "讓那個斷掉的第 12 個音能響起來。")
    assert t and "現在能完整地響" in t, t
