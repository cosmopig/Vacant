"""W3（2026-10-01）：分身住進世界——WORLD.md 是前提不是菜單；指令不給任何任務方向。"""
from __future__ import annotations

import hashlib
import pathlib
import re

import pytest

from ops.exhibit.twin import twinagent
from vacant_network.memory import KS1Violation, assert_ks1_clean

WORLD = pathlib.Path(twinagent.WORLD_PATH)

#: 世界外的詞（世界內文字與分身指令都不准出現；指令裡的「AI／模型」只在「不要自稱／不要提到」的禁令句裡）
_OUTSIDE = ("AI", "模型", "agent", "Agent", "驗證", "信任", "系統", "任務", "用戶", "專案", "使用者")
#: 菜單句式：WORLD.md 只寫事實與摩擦，不寫「可以做 X」「需要有人 Y」
_MENU = ("可以做", "需要有人", "需要", "可以去", "不妨", "建議", "待辦", "任務清單", "小事清單", "要有人")
#: 黑夜／時段詞（v2：這個世界沒有黑夜）
_TIME = ("白天", "晚上", "夜", "早上", "黃昏", "日落", "日出")
#: v2 第 3 節那 22 件小事的關鍵詞：指令裡出現＝在替分身指任務方向
_CHORE_WORDS = ("攤平", "鐵環", "削尖", "木花", "紙團", "筆筒", "抹平", "裂了縫", "折成三折", "數過",
                "墊一小塊", "吹掉", "按日期", "抄一張", "清單", "分開", "換上", "量一量", "托盤",
                "掃進", "翻出", "擦乾淨", "找出不一樣", "轉一圈", "照長短", "排好", "收好")


def test_world_has_no_outside_words_no_menu_no_time() -> None:
    t = WORLD.read_text(encoding="utf-8")
    assert [w for w in _OUTSIDE if w in t] == []
    assert [w for w in _MENU if w in t] == []
    assert [w for w in _TIME if w in t] == []
    assert not re.search(r"(可以|能夠|應該|必須).{0,6}(做|去|幫|替)", t)
    assert_ks1_clean(t)
    # 負控制：這把尺量得到
    assert [w for w in _MENU if w in "這裡需要有人把鏈量一量"] != []
    with pytest.raises(KS1Violation):
        assert_ks1_clean(t + "你有責任把它做完")


def test_world_has_eight_places_and_no_friction_menu_section() -> None:
    """W3b：「這個世界現在的樣子」那 14 條被當成菜單，整節刪掉；摩擦改由地上的實物自己呈現。"""
    t = WORLD.read_text(encoding="utf-8")
    for place in ("投遞口", "捏土處", "長桌廣場", "石頭閘門", "帳本鏈", "草稿角", "紙卡地", "畫架與長椅"):
        assert place in t, place
    assert "# 規矩和習俗" in t and "# 新來的人" in t and "# 住在這裡的人" in t
    assert "這個世界現在的樣子" not in t
    assert not [ln for ln in t.splitlines() if ln.startswith("- ")], "WORLD.md 不放條列摩擦"


def test_world_is_not_the_v2_chore_list() -> None:
    """v2 那 22 件小事不准放進 WORLD.md（放了＝菜單）：沒有編號清單形式的小事。"""
    t = WORLD.read_text(encoding="utf-8")
    assert "小事清單" not in t and "22 件" not in t
    assert "這個世界現在的樣子" not in t


def test_system_prompt_has_no_task_direction() -> None:
    p = (twinagent.SYSTEM_PROMPT + twinagent.FIRST_MESSAGE
         + twinagent.LETTER_SYSTEM_PROMPT + twinagent.LETTER_FIRST_MESSAGE)
    assert [w for w in _CHORE_WORDS if w in p] == []
    for bad in ("例如", "比如", "譬如", "像是", "一封信", "一份計畫", "一張清單", "謝卡"):
        assert bad not in p
    # 負控制
    assert [w for w in _CHORE_WORDS if w in "把一張紙攤平"] != []


def test_system_prompt_world_premise_and_complexity_conditions() -> None:
    p = twinagent.SYSTEM_PROMPT
    for must in ("信.md", "WORLD.md", "地上/", "走進了這個世界", "只可能發生在這個世界裡", "不是誰走進來都會想的",
                 "三個想要", "兩件東西之間的關聯", "至少三件東西",
                 "至少兩個地點", "共用的東西", "別的居民", "一條世界的規矩", "好幾步", "還沒做完",
                 "如果你在這裡", "它牽動到", "步驟", "做完的樣子", "成品至少兩個檔", "ws_list 看一次房間", "不要自稱 AI",
                 "每一次動手", "不要寫程式", "現實生活"):
        assert must in p, must
    assert "TRAITS.md" not in p, "段 2 的房間裡沒有 TRAITS.md，指令不提它"
    for t in (twinagent.SYSTEM_PROMPT, twinagent.FIRST_MESSAGE, twinagent.CALLER_PROMPT):
        assert_ks1_clean(t)


def test_world_sha_and_notartifact() -> None:
    assert twinagent.world_sha256() == hashlib.sha256(WORLD.read_bytes()).hexdigest()
    assert "WORLD.md" in twinagent.NOT_ARTIFACTS


def test_world_classified_other_not_artifact() -> None:
    from ops.exhibit.twin import sidecar
    assert sidecar.classify_path_kind("ws_read", "WORLD.md") == "other"
    assert sidecar.classify_path_kind("ws_read", "TRAITS.md") == "traits"
