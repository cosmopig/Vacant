"""P10 線 F（2026-10-02）：命盤——只決定「做事的方式」、不決定題目；命盤卡每一句要有步驟根據。

守的是：
* 資料契約：枚舉收斂、星座與血型沒給就不猜（TRAITS、信的命盤段、命盤卡三處都擋）、MBTI 沒給才收分身猜的；
* 對照表（`fortune_text.py`）：每一條都乾淨（KS-1、無世界外的詞、無任務例子／菜單、≤70 字），三種命盤組合都拼得出來、
  J 與 P 的段落不同（劇本不一樣）、沒有命盤時段 2 的系統提示與沒有這個功能時逐位元相同；
* 命盤卡：每一句對步驟紀錄——找不到根據的句子拿掉（有負控制：同一句在有紀錄時保留）；
* 旁註 `twin_fortune` 與電視契約：全是枚舉、card 拍才有句子、有牙齒；
* 撤回：`fortune` 進檔案庫（不在鏈上）、run-dir 的檔整個刪。
"""
from __future__ import annotations

import itertools
import json
import pathlib
import re
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ops.exhibit.twin import fortune as fz                           # noqa: E402
from ops.exhibit.twin import fortune_text as T                       # noqa: E402
from ops.exhibit.twin import grounding_gate as gg                    # noqa: E402
from ops.exhibit.twin import live_events as le                       # noqa: E402
from ops.exhibit.twin import sidecar as sc                           # noqa: E402
from ops.exhibit.twin import tv_contract as tv                       # noqa: E402
from ops.exhibit.twin import twin_letter_guard as guard              # noqa: E402
from ops.exhibit.twin import twinagent, twinvault                    # noqa: E402
from vacant_network.vrun import lifecycle                            # noqa: E402

TWIN = ROOT / "ops" / "exhibit" / "twin"
FULL = {"mbti": "INFP", "mbti_source": "ai", "zodiac": "雙魚", "blood": "O"}


# ---------------------------------------------------------------------------
# 資料契約
# ---------------------------------------------------------------------------

def test_normalize_keeps_only_enumerations() -> None:
    assert fz.normalize(FULL) == FULL
    assert fz.normalize({"mbti": "INFP", "mbti_source": "self"})["mbti_source"] == "self"
    n = fz.normalize({"mbti": "XXXX", "mbti_source": "ai", "zodiac": "火星", "blood": "C"})
    assert n == {"mbti": None, "mbti_source": None, "zodiac": None, "blood": None}
    assert fz.normalize(None) == fz.normalize("垃圾") == {"mbti": None, "mbti_source": None, "zodiac": None, "blood": None}
    # mbti_source 缺／不認得 ⇒ 以 ai 計（卡片只有 ai／self）；但 twin 不是卡片會有的值
    assert fz.normalize({"mbti": "ENTJ", "mbti_source": "twin"})["mbti_source"] == "ai"


def test_elements_cover_the_twelve_signs_three_each() -> None:
    assert set(fz.ELEMENT_OF) == set(fz.ZODIACS) and len(fz.ZODIACS) == 12
    assert sorted(fz.ELEMENT_OF.values()) == ["土"] * 3 + ["水"] * 3 + ["火"] * 3 + ["風"] * 3


def test_traits_lines_say_not_given_and_forbid_guessing_zodiac_and_blood() -> None:
    given = "\n".join(fz.traits_lines(FULL))
    assert "INFP（觀眾的 AI 說的）" in given and "星座：雙魚" in given and "血型：O" in given
    none = "\n".join(fz.traits_lines(fz.normalize(None)))
    assert "MBTI：沒有給（請你依特質猜" in none
    assert "星座：沒有給（不要猜" in none and "血型：沒有給（不要猜" in none
    assert "觀眾自己選的" in "\n".join(fz.traits_lines({"mbti": "ENFP", "mbti_source": "self"}))


def test_render_traits_carries_the_fortune_lines() -> None:
    t = twinagent.render_traits({"need": "x", **FULL}, "")
    assert "- MBTI：INFP" in t and "- 星座：雙魚" in t and "- 血型：O" in t
    t2 = twinagent.render_traits({"need": "x"}, "")
    assert "星座：沒有給（不要猜" in t2


def test_first_line_omits_what_was_not_given() -> None:
    assert fz.first_line(FULL) == "INFP · 雙魚（水）· O 型"
    assert fz.first_line({"mbti": "ISTJ", "zodiac": None, "blood": None}) == "ISTJ"
    assert fz.first_line({"mbti": None, "zodiac": "獅子", "blood": "AB"}) == "獅子（火）· AB 型"
    assert fz.first_line(fz.normalize(None)) == ""


# ---------------------------------------------------------------------------
# 信的命盤段
# ---------------------------------------------------------------------------

LETTER = (
    "這個人手慢，愛安靜，在意東西有沒有放回原處。\n\n命盤\nMBTI：INFP\n依據：安靜又在意別人的心情\n"
    "E/I：話不多，待在角落看人\nS/N：比起清點，更愛想像還沒成形的東西\nT/F：先想到的是別人的心情\n"
    "J/P：計畫寫了又改，邊走邊定\n星座：慢慢滲進土裡的水\n血型：看起來很穩\n"
)


def test_parse_letter_splits_body_and_section() -> None:
    body, sec = fz.parse_letter(LETTER)
    assert body.startswith("這個人手慢") and "命盤" not in body
    assert sec["mbti"] == "INFP" and sec["EI"].startswith("話不多") and sec["JP"].startswith("計畫")
    assert fz.parse_letter("沒有命盤的信")[1] == {}
    assert fz.parse_letter("本文\n## 命盤\n**MBTI**：ENTP")[1]["mbti"] == "ENTP"


def test_guess_mbti_needs_exactly_a_sixteen_type_not_a_longer_word() -> None:
    assert fz.guess_mbti({"mbti": "我猜是 intj。"}) == "INTJ"
    assert fz.guess_mbti({"mbti": "INFPointer"}) is None
    assert fz.guess_mbti({"mbti": "XXXX"}) is None and fz.guess_mbti({}) is None


def test_resolve_given_beats_guess_and_guess_is_marked_twin() -> None:
    sec = {"mbti": "ENTP"}
    g = fz.resolve(FULL, sec)
    assert g["mbti"] == "INFP" and g["mbti_source"] == "ai" and g["mbti_guessed"] is False and g["element"] == "水"
    g2 = fz.resolve(fz.normalize({"zodiac": "獅子"}), sec)
    assert g2["mbti"] == "ENTP" and g2["mbti_source"] == "twin" and g2["mbti_guessed"] is True and g2["element"] == "火"
    g3 = fz.resolve(fz.normalize(None), {})
    assert g3["mbti"] is None and not fz.has_any(g3)


def test_render_section_given_all_writes_headers_itself_and_keeps_sentences() -> None:
    _b, sec = fz.parse_letter(LETTER)
    f = fz.resolve(FULL, sec)
    text, cnt = fz.render_section(f, sec, "")
    lines = text.splitlines()
    assert lines[0] == "命盤"
    assert lines[1] == "MBTI：你是 INFP（你的 AI 這麼說）"
    assert any(x.startswith("E/I：話不多") for x in lines)
    assert any(x.startswith("星座：雙魚（水象）。") for x in lines)
    assert any(x.startswith("血型：O 型。") for x in lines)
    assert cnt["dropped"] == []


def test_render_section_guess_has_basis_line_and_says_guess() -> None:
    _b, sec = fz.parse_letter(LETTER)
    f = fz.resolve(fz.normalize(None), sec)
    text, _ = fz.render_section(f, sec, "")
    assert "MBTI：我猜你是 INFP。依據：安靜又在意別人的心情" in text
    # 星座血型沒給：整行不寫（分身寫了也被拿掉），不猜
    assert "星座" not in text and "血型" not in text


def test_render_section_drops_ungiven_leak_and_time_sentences() -> None:
    sec = {"mbti": "INFP", "EI": "像個雙魚座的人，愛躲起來", "SN": "每天早上都在想像", "TF": "把心情看得比東西重要得多得多",
           "JP": "他其實是 A 型的計畫派", "zodiac": "水象", "blood": "穩穩的 O 型"}
    f = fz.resolve(fz.normalize({"mbti": "INFP"}), sec)
    text, cnt = fz.render_section(f, sec, traits="把心情看得比東西重要得多得多")
    why = {d["key"]: d["why"] for d in cnt["dropped"]}
    assert why == {"EI": "ungiven", "SN": "time", "TF": "leak", "JP": "ungiven"}, why
    assert text.splitlines() == ["命盤", "MBTI：你是 INFP（你的 AI 這麼說）"]
    # 負控制：同樣的句子在「有給」時不會被 ungiven 擋
    f2 = fz.resolve(fz.normalize({"mbti": "INFP", "zodiac": "雙魚", "blood": "A"}), {})
    _t, cnt2 = fz.render_section(f2, {"EI": "像個雙魚座的人，愛躲起來", "JP": "他其實是 A 型的計畫派"}, "")
    assert not [d for d in cnt2["dropped"] if d["why"] == "ungiven"]


def test_render_section_empty_when_nothing_to_write() -> None:
    f = fz.resolve(fz.normalize(None), {})
    assert fz.render_section(f, {}, "") == ("", {"lines": 0, "dropped": []})


def test_clean_sentence_cuts_long_ones_at_punctuation() -> None:
    s, why = fz.clean_sentence("慢慢地把每一件東西放回它原來的位置，再看一眼才肯離開，而且不會對任何人說起這件事。", "", FULL)
    assert why is None and len(s) <= fz.MAX_SENTENCE and not s.endswith("，")


def test_letter_guard_writes_final_letter_with_rewritten_section_and_fortune_final(tmp_path) -> None:
    ws, rd = tmp_path / "ws", tmp_path / "rd"
    ws.mkdir(), rd.mkdir()
    (ws / "TRAITS.md").write_text("# 這位觀眾的特質\n- 氣質：慢\n", encoding="utf-8")
    (ws / "信.md").write_text(LETTER, encoding="utf-8")
    (rd / fz.IN_NAME).write_text(json.dumps(fz.normalize({"zodiac": "雙魚"})), encoding="utf-8")
    assert guard.run(ws, rd) == 0
    final = (ws / "信.md").read_text(encoding="utf-8")
    assert "MBTI：我猜你是 INFP。依據：" in final and "星座：雙魚（水象）" in final
    assert "血型" not in final                      # 沒給就不寫
    assert (rd / "letter_final.md").read_text(encoding="utf-8") == final
    f = fz.load_final(rd)
    assert (f["mbti"], f["mbti_source"], f["zodiac"], f["blood"], f["element"]) == ("INFP", "twin", "雙魚", None, "水")
    info = json.loads((rd / "letter_guard.json").read_text(encoding="utf-8"))
    assert info["fortune"]["mbti_guessed"] is True and "TRAITS" not in json.dumps(info)
    assert not (ws / "TRAITS.md").exists()


def test_letter_guard_body_limit_still_300_and_section_not_counted(tmp_path) -> None:
    ws, rd = tmp_path / "ws", tmp_path / "rd"
    ws.mkdir(), rd.mkdir()
    (ws / "TRAITS.md").write_text("x", encoding="utf-8")
    long_body = "安靜的人。" * 100
    (ws / "信.md").write_text(long_body + "\n命盤\nMBTI：ISTJ\nE/I：話少", encoding="utf-8")
    assert guard.run(ws, rd) == 0
    body, sec = fz.parse_letter((ws / "信.md").read_text(encoding="utf-8"))
    assert len(body) <= guard.MAX_LETTER and "E/I" in (ws / "信.md").read_text(encoding="utf-8")


def test_letter_without_section_still_works_and_no_fortune_means_no_way(tmp_path) -> None:
    ws, rd = tmp_path / "ws", tmp_path / "rd"
    ws.mkdir(), rd.mkdir()
    (ws / "TRAITS.md").write_text("x", encoding="utf-8")
    (ws / "信.md").write_text("這個人手慢而且安靜。", encoding="utf-8")
    assert guard.run(ws, rd) == 0
    f = fz.load_final(rd)
    assert f is not None and not fz.has_any(f)
    assert fz.way_text(f) == ""
    out = subprocess.run([sys.executable, str(TWIN / "fortune.py"), "way", str(rd)], capture_output=True, text=True)
    assert out.returncode == 0 and out.stdout == ""


# ---------------------------------------------------------------------------
# 對照表（做事的方式）
# ---------------------------------------------------------------------------

_OUTSIDE = ("AI", "模型", "agent", "Agent", "提示詞", "驗證", "信任", "系統", "任務", "使用者", "專案", "用戶")
_TIME = ("白天", "晚上", "夜", "早上", "黃昏", "日落", "日出", "凌晨")
_MENU = ("例如", "比如", "可以做", "待辦", "任務清單", "小事清單")


def _all_texts() -> list[tuple[str, str]]:
    out = [("WAY_INTRO", T.WAY_INTRO)]
    for name in ("WAY_EI", "WAY_SN", "WAY_TF", "WAY_JP", "WAY_ELEMENT", "WAY_BLOOD", "RETRY_JP", "FIRST_STOPS"):
        out += [(f"{name}[{k}]", v) for k, v in getattr(T, name).items()]
    out.append(("CARD_RULES", fz.CARD_RULES))
    return out


def test_table_has_every_key() -> None:
    assert set(T.WAY_EI) == {"E", "I"} and set(T.WAY_SN) == {"S", "N"}
    assert set(T.WAY_TF) == {"T", "F"} and set(T.WAY_JP) == {"J", "P"} and set(T.RETRY_JP) == {"J", "P"}
    assert set(T.WAY_ELEMENT) == {"火", "土", "風", "水"} and set(T.WAY_BLOOD) == {"A", "B", "O", "AB"}
    assert set(T.FIRST_STOPS) == {"ES", "EN", "IS", "IN"}


def test_every_way_text_is_clean_short_and_in_the_world() -> None:
    from vacant_network.memory import assert_ks1_clean
    for name, t in _all_texts():
        assert t.strip(), name
        assert not [w for w in _OUTSIDE if w in t], (name, [w for w in _OUTSIDE if w in t])
        assert not [w for w in _TIME if w in t], (name, [w for w in _TIME if w in t])
        assert not [w for w in _MENU if w in t], (name, "任務例子／菜單", [w for w in _MENU if w in t])
        assert_ks1_clean(t)
        if name != "CARD_RULES":
            assert len(t) <= 160, (name, len(t))
        assert not re.search(r"[\U0001F300-\U0001FAFF☀-➿]", t), name


def test_first_stops_name_three_real_places_each_in_the_agreed_order() -> None:
    want = {"ES": ("長桌廣場", "投遞口", "捏土處"), "EN": ("畫架與長椅", "投遞口", "長桌廣場"),
            "IS": ("帳本鏈", "紙卡地", "石頭閘門"), "IN": ("草稿角", "紙卡地", "畫架與長椅")}
    for k, places in want.items():
        t = T.FIRST_STOPS[k]
        idx = [t.index(p) for p in places]
        assert idx == sorted(idx), (k, t)
        assert all(p in fz.PLACES for p in places)


def test_way_text_for_all_combinations_is_deterministic_and_nonempty() -> None:
    n = 0
    for m, z, b in itertools.product(fz.MBTI_TYPES, (None, "牡羊", "金牛", "雙子", "雙魚"), (None, "A", "B", "O", "AB")):
        f = {"mbti": m, "zodiac": z, "blood": b}
        a, a2 = fz.way_text(f), fz.way_text(dict(f))
        assert a == a2 and a.startswith("\n\n") and fz.CARD_RULES in a
        n += 1
    assert n == 16 * 5 * 5
    # 只有星座、只有血型也有（不靠 MBTI）
    assert T.WAY_ELEMENT["水"] in fz.way_text({"mbti": None, "zodiac": "雙魚", "blood": None})
    assert T.WAY_BLOOD["AB"] in fz.way_text({"mbti": None, "zodiac": None, "blood": "AB"})


def test_no_fortune_means_empty_way_and_identical_stage2_argv() -> None:
    assert fz.way_text({"mbti": None, "zodiac": None, "blood": None}) == ""
    assert fz.reminder({"mbti": None, "zodiac": None, "blood": None}) == "" and fz.reminder({"blood": "O"}) != ""
    assert fz.way_lines({}) == []


def test_j_and_p_get_different_plan_order_and_different_retry_ways() -> None:
    j = fz.way_text({"mbti": "ISTJ"})
    p = fz.way_text({"mbti": "ISTP"})
    assert T.WAY_JP["J"] in j and T.WAY_JP["P"] not in j
    assert T.WAY_JP["P"] in p and T.WAY_JP["J"] not in p
    assert T.RETRY_JP["J"] in j and T.RETRY_JP["P"] in p and T.WAY_JP["J"] != T.WAY_JP["P"]
    assert T.RETRY_JP["J"] != T.RETRY_JP["P"]


def test_the_ways_give_no_task_examples_and_never_name_zodiac_or_viewer_words() -> None:
    blob = "".join(t for _n, t in _all_texts())
    assert not [z for z in fz.ZODIACS if z in blob], "對照表裡出現星座名（元素用火土風水就好）"
    assert "MBTI" not in blob


def test_stage2_system_prompt_still_has_no_examples_and_wrapper_appends_way() -> None:
    sh = (TWIN / "twin_agent.sh").read_text(encoding="utf-8")
    assert 'fortune.py" way "$RUN_DIR"' in sh and 'SYS="$SYS$WAY"' in sh
    assert 'fortune.py" announce "$RUN_DIR"' in sh and 'fortune.py" card "$(pwd)" "$RUN_DIR"' in sh
    # 順序：關卡 → way → 預算 → pi 段 2 → card → prepare
    assert sh.index("twin_letter_guard.py") < sh.index('SYS="$SYS$WAY"') < sh.index("runlimited") \
        < sh.index('fortune.py" card') < sh.index("grounding_gate.py\" prepare")
    assert "命盤" in twinagent.LETTER_SYSTEM_PROMPT and "不要猜" in twinagent.LETTER_SYSTEM_PROMPT


def test_wrapper_stage2_argv_gets_the_way_through_a_real_shell_run(tmp_path) -> None:
    """真的跑 `twin_agent.sh`（假 pi 把收到的 --system-prompt 寫下來）：命盤的做事方式有進段 2，沒有命盤就逐位元不變。"""
    import os
    import shutil
    for name, f, want_way in (("with", FULL, True), ("without", fz.normalize(None), False)):
        base = tmp_path / name
        ws, rd = base / "ws", base / "rd"
        ws.mkdir(parents=True), rd.mkdir(parents=True)
        (ws / "TRAITS.md").write_text("- 氣質：慢\n", encoding="utf-8")
        (rd / fz.IN_NAME).write_text(json.dumps(f), encoding="utf-8")
        (rd / "stage2_in").mkdir()
        (rd / "stage2_in" / "WORLD.md").write_text("世界\n", encoding="utf-8")
        (rd / "stage2_in" / "地上").mkdir()
        (rd / "stage2_in" / "地上" / "a.txt").write_text("x\n", encoding="utf-8")
        fake = base / "pi"
        fake.write_text(
            "#!/usr/bin/env bash\n"
            "LAST=\"\"; while [ $# -gt 0 ]; do case \"$1\" in --system-prompt) SP=\"$2\"; shift 2;; *) LAST=\"$1\"; shift;; esac; done\n"
            f"if [ -f 信.md ]; then printf '%s' \"$SP\" > {rd}/sys2.txt; printf '%s' \"$LAST\" > {rd}/msg2.txt; else printf '我猜\\n' > /dev/null;"
            " printf '這個人手慢。\\n\\n命盤\\nMBTI：INFP\\nE/I：話少\\n' > 信.md; fi\n",
            encoding="utf-8")
        fake.chmod(0o755)
        env = {**os.environ, "VACANT_RUN_PROXY": "http://127.0.0.1:1", "VACANT_TWIN_PI": str(fake),
               "VACANT_TWIN_PY": sys.executable}
        r = subprocess.run(["bash", str(TWIN / "twin_agent.sh"), "S1", "M1", str(rd), "BASE-SYS", "MSG"],
                           cwd=ws, env=env, capture_output=True, text=True, timeout=60)
        assert r.returncode == 0, r.stderr
        sys2 = (rd / "sys2.txt").read_text(encoding="utf-8")
        msg2 = (rd / "msg2.txt").read_text(encoding="utf-8")
        if want_way:
            assert sys2.startswith("BASE-SYS\n\n" + T.WAY_INTRO) and (T.WAY_JP["J"] in sys2 or T.WAY_JP["P"] in sys2)
            assert fz.CARD_RULES in sys2 and msg2 == "MSG\n" + fz.CARD_REMINDER
        else:
            # 沒給任何命盤，但分身猜了 MBTI（信裡寫了 INFP）⇒ 也有做事的方式（猜的也算）
            assert sys2.startswith("BASE-SYS") and msg2.startswith("MSG")
        shutil.rmtree(base, ignore_errors=True)


def test_wrapper_without_any_fortune_leaves_stage2_system_prompt_bit_identical(tmp_path) -> None:
    import os
    ws, rd = tmp_path / "ws", tmp_path / "rd"
    ws.mkdir(), rd.mkdir()
    (ws / "TRAITS.md").write_text("- 氣質：慢\n", encoding="utf-8")
    (rd / fz.IN_NAME).write_text(json.dumps(fz.normalize(None)), encoding="utf-8")
    (rd / "stage2_in").mkdir()
    (rd / "stage2_in" / "WORLD.md").write_text("世界\n", encoding="utf-8")
    (rd / "stage2_in" / "地上").mkdir()
    fake = tmp_path / "pi"
    fake.write_text(
        "#!/usr/bin/env bash\n"
        "LAST=\"\"; while [ $# -gt 0 ]; do case \"$1\" in --system-prompt) SP=\"$2\"; shift 2;; *) LAST=\"$1\"; shift;; esac; done\n"
        f"if [ -f 信.md ]; then printf '%s' \"$SP\" > {rd}/sys2.txt; printf '%s' \"$LAST\" > {rd}/msg2.txt; else printf '這個人手慢。\\n' > 信.md; fi\n",
        encoding="utf-8")
    fake.chmod(0o755)
    env = {**os.environ, "VACANT_RUN_PROXY": "http://127.0.0.1:1", "VACANT_TWIN_PI": str(fake),
           "VACANT_TWIN_PY": sys.executable}
    r = subprocess.run(["bash", str(TWIN / "twin_agent.sh"), "S1", "M1", str(rd), "BASE-SYS", "MSG"],
                       cwd=ws, env=env, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    assert (rd / "sys2.txt").read_text(encoding="utf-8") == "BASE-SYS"
    assert (rd / "msg2.txt").read_text(encoding="utf-8") == "MSG"


# ---------------------------------------------------------------------------
# 命盤卡：每一句要有步驟根據
# ---------------------------------------------------------------------------

def _row(i, tool, path, ok=True):
    return {"ts_ms": 1000 + i, "seq": i, "tool": tool, "path": path, "bytes": 10, "ok": ok}


def _steps(rd: pathlib.Path, rows) -> None:
    (rd / fz.STEP_LOG_NAME).write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")


def _world(tmp_path, rows, *, card: str | None, files: dict[str, str] | None = None):
    rd, ws = tmp_path / "rd", tmp_path / "ws"
    rd.mkdir(), ws.mkdir()
    _steps(rd, rows)
    for name, t in (files or {}).items():
        (ws / name).write_text(t, encoding="utf-8")
    if card is not None:
        (ws / fz.CARD_FILE).write_text(card, encoding="utf-8")
    return rd, ws


STAGE1 = [_row(1, "ws_read", "TRAITS.md"), _row(2, "ws_write", "信.md")]
BROWSE_THEN_PLAN = STAGE1 + [
    _row(3, "ws_read", "信.md"), _row(4, "ws_read", "WORLD.md"), _row(5, "ws_list", "地上"),
    _row(6, "ws_read", "地上/草稿角/紙團_乙.txt"), _row(7, "ws_read", "地上/帳本鏈/尾段_418到447片.txt"),
    _row(8, "ws_write", "PLAN.md"), _row(9, "ws_write", "成品.md"), _row(10, "ws_list", "."),
]
PLAN_THEN_BROWSE = STAGE1 + [
    _row(3, "ws_read", "信.md"), _row(4, "ws_read", "WORLD.md"), _row(5, "ws_list", "地上"),
    _row(6, "ws_write", "PLAN.md"), _row(7, "ws_read", "地上/紙卡地/格狀圖.txt"), _row(8, "ws_write", "成品.md"),
]


def test_visited_places_in_order_only_stage2_and_only_ok_reads() -> None:
    rows = BROWSE_THEN_PLAN + [_row(11, "ws_read", "地上/投遞口/x.txt", ok=False)]
    assert fz.visited_places(rows) == ["草稿角", "帳本鏈"]
    assert fz.visited_places(PLAN_THEN_BROWSE) == ["紙卡地"]


def test_card_keeps_grounded_sentences_and_drops_the_rest(tmp_path) -> None:
    card = ("INFP · 雙魚（水）· O 型\n"
            "你偏安靜，所以我先去了草稿角。\n"                     # 去過 ✓
            "你愛想像，所以我先走過地上才寫計畫。\n"                 # 先逛 ✓（讀在寫 PLAN 之前）
            "你在意別人的心情，所以我去了投遞口。\n"                 # 沒去過 ✗
            "你很穩，所以我寫了計畫。\n")                           # ✓ 但已滿 2 句…仍在上限內（第 3 句）
    rd, ws = _world(tmp_path, BROWSE_THEN_PLAN, card=card)
    res = fz.build_card(rd, ws, fz.resolve(FULL, {}))
    assert res["first_line"] == "INFP · 雙魚（水）· O 型"
    assert [x for x in res["lines"]] == ["你偏安靜，所以我先去了草稿角。", "你愛想像，所以我先走過地上才寫計畫。",
                                         "你很穩，所以我寫了計畫。"]
    assert res["dropped"] == [{"text": "你在意別人的心情，所以我去了投遞口。", "why": "ungrounded:投遞口"}]
    assert res["present"] is True and res["places"] == ["草稿角", "帳本鏈"]
    assert json.loads((rd / fz.CARD_JSON_NAME).read_text(encoding="utf-8"))["dropped"]


def test_card_negative_control_same_sentence_is_kept_once_the_step_exists(tmp_path) -> None:
    sent = "你在意別人的心情，所以我去了投遞口。"
    rd, ws = _world(tmp_path / "a", BROWSE_THEN_PLAN, card=sent) if False else (None, None)
    (tmp_path / "a").mkdir(), (tmp_path / "b").mkdir()
    rd, ws = _world(tmp_path / "a", BROWSE_THEN_PLAN, card=sent)
    assert fz.build_card(rd, ws, fz.resolve(FULL, {}))["lines"] == []
    rows = BROWSE_THEN_PLAN + [_row(11, "ws_read", "地上/投遞口/收據卡_蕨葉.txt")]
    rd2, ws2 = _world(tmp_path / "b", rows, card=sent)
    assert fz.build_card(rd2, ws2, fz.resolve(FULL, {}))["lines"] == [sent]


def test_order_claims_follow_the_actual_order(tmp_path) -> None:
    j_claim = "你愛先想清楚，所以我先寫計畫再動手。"
    p_claim = "你愛邊走邊看，所以我先逛了地上才寫計畫。"
    (tmp_path / "x").mkdir(), (tmp_path / "y").mkdir()
    for sub, rows, ok_line, bad_line in (("x", PLAN_THEN_BROWSE, j_claim, p_claim),
                                         ("y", BROWSE_THEN_PLAN, p_claim, j_claim)):
        rd, ws = _world(tmp_path / sub, rows, card=ok_line + "\n" + bad_line)
        res = fz.build_card(rd, ws, fz.resolve(FULL, {}))
        assert res["lines"] == [ok_line], (sub, res)
        assert [d["text"] for d in res["dropped"]] == [bad_line]


def test_changed_mind_needs_two_plan_writes_and_two_versions_needs_both_files(tmp_path) -> None:
    mind = "你容易反悔，所以我改了主意。"
    two = "你想兩全，所以我做了兩個版本。"
    (tmp_path / "a").mkdir(), (tmp_path / "b").mkdir()
    rd, ws = _world(tmp_path / "a", BROWSE_THEN_PLAN, card=mind + "\n" + two,
                    files={"一.md": "版本一\n x", "二.md": "版本二\n y"})
    res = fz.build_card(rd, ws, fz.resolve(FULL, {}))
    assert res["lines"] == [two] and res["dropped"][0]["why"] == "ungrounded:改了主意"
    rows = BROWSE_THEN_PLAN + [_row(11, "ws_write", "PLAN.md")]
    rd2, ws2 = _world(tmp_path / "b", rows, card=mind, files={"成品.md": "x"})
    assert fz.build_card(rd2, ws2, fz.resolve(FULL, {}))["lines"] == [mind]


def test_card_drops_shape_unverifiable_ungiven_leak_time_and_too_long(tmp_path) -> None:
    f = fz.resolve({"mbti": "INFP", "mbti_source": "ai", "zodiac": None, "blood": None}, {})
    card = ("INFP\n"
            "我去了草稿角\n"                                   # shape：不是「你…所以我…」
            "你很特別，所以我做了一些事。\n"                       # no_checkable
            "你像個雙魚座的人，所以我去了草稿角。\n"                 # ungiven（沒給星座）
            "你是 O 型的人，所以我去了草稿角。\n"                   # ungiven（沒給血型）
            "你喜歡安靜，所以我每天早上去了草稿角。\n"                # time
            "你很好，所以我去了草稿角" + "，也很用心地做了很多事" * 6 + "。\n")   # too_long
    rd, ws = _world(tmp_path, BROWSE_THEN_PLAN, card=card)
    res = fz.build_card(rd, ws, f)
    assert res["lines"] == []
    assert [d["why"] for d in res["dropped"]] == ["no_checkable", "ungiven", "ungiven", "time", "too_long"]


def test_card_cannot_claim_a_gate_result_or_receipt(tmp_path) -> None:
    bad = ["你求穩，所以我將這份東西送入石頭閘門並獲得了收據。", "你求穩，所以我在石頭閘門通過了檢查。"]
    rows = BROWSE_THEN_PLAN + [_row(11, "ws_read", "地上/石頭閘門/窗格亮滅.txt")]
    rd, ws = _world(tmp_path, rows, card="\n".join(bad))
    res = fz.build_card(rd, ws, fz.resolve(FULL, {}))
    assert res["lines"] == [] and [d["why"] for d in res["dropped"]] == ["receipt_claim"] * 2
    (tmp_path / "ok").mkdir()
    rd2, ws2 = _world(tmp_path / "ok", rows, card="你求穩，所以我讀了石頭閘門旁邊的窗格紀錄。")
    assert len(fz.build_card(rd2, ws2, fz.resolve(FULL, {}))["lines"]) == 1
    # 提到「收據」這個東西本身不算（帳本鏈上本來就有收據片）
    (tmp_path / "ok2").mkdir()
    rd3, ws3 = _world(tmp_path / "ok2", rows, card="你愛核對，所以我記錄了帳本鏈上的鬆環與收據關聯。")
    assert len(fz.build_card(rd3, ws3, fz.resolve(FULL, {}))["lines"]) == 1


def test_card_leak_is_against_the_viewers_original_not_against_the_letter(tmp_path) -> None:
    """卡句的 X 本來就是從信讀來的性情（信已過 LEAK）；要擋的是逐字抄了觀眾原文（run-dir 的 traits_ref.txt）。"""
    sent = "你把東西放回原處才安心，所以我先去了草稿角。"
    rd, ws = _world(tmp_path, BROWSE_THEN_PLAN, card=sent)
    (rd / "letter_final.md").write_text("他把東西放回原處才安心的人。", encoding="utf-8")
    assert fz.traits_hint(rd) == ""
    assert fz.build_card(rd, ws, fz.resolve(FULL, {}), fz.traits_hint(rd))["lines"] == [sent]      # 抄信不算
    (rd / "traits_ref.txt").write_text("- 氣質：把東西放回原處才安心，慢", encoding="utf-8")
    res = fz.build_card(rd, ws, fz.resolve(FULL, {}), fz.traits_hint(rd))
    assert res["lines"] == [] and res["dropped"][0]["why"] == "leak"


def test_letter_guard_keeps_a_traits_copy_in_the_run_dir_only(tmp_path) -> None:
    ws, rd = tmp_path / "ws", tmp_path / "rd"
    ws.mkdir(), rd.mkdir()
    (ws / "TRAITS.md").write_text("# 特質\n- 氣質：慢而固執\n", encoding="utf-8")
    (ws / "信.md").write_text("這個人手慢。", encoding="utf-8")
    assert guard.run(ws, rd) == 0
    assert "慢而固執" in (rd / "traits_ref.txt").read_text(encoding="utf-8")
    assert not (ws / "TRAITS.md").exists() and not list(ws.rglob("traits_ref*"))


def test_card_max_three_lines_and_first_line_is_deterministic_not_the_twins(tmp_path) -> None:
    ls = "\n".join("你一，所以我先去了草稿角。" for _ in range(5))
    rd, ws = _world(tmp_path, BROWSE_THEN_PLAN, card="我自己亂寫的第一行\n" + ls)
    res = fz.build_card(rd, ws, fz.resolve(FULL, {}))
    assert len(res["lines"]) == 3 and [d["why"] for d in res["dropped"]] == ["over_limit"] * 2
    assert fz.card_md(res).splitlines()[0] == "INFP · 雙魚（水）· O 型"
    assert "亂寫" not in fz.card_md(res) and len(fz.card_md(res).splitlines()) <= 6


def test_no_fortune_no_card_and_missing_card_file_is_not_a_crash(tmp_path) -> None:
    rd, ws = _world(tmp_path, BROWSE_THEN_PLAN, card="你好，所以我先去了草稿角。")
    assert fz.build_card(rd, ws, fz.resolve(fz.normalize(None), {}))["present"] is False
    (tmp_path / "n").mkdir()
    rd2, ws2 = _world(tmp_path / "n", BROWSE_THEN_PLAN, card=None)
    r = fz.build_card(rd2, ws2, fz.resolve(FULL, {}))
    assert r["present"] is False and r["card_file"] is False and r["first_line"]


def test_left_for_accepts_a_note_file_named_for_someone(tmp_path) -> None:
    claim = "你照顧別人，所以我留給了苔綠細長一張紙條。"
    rd, ws = _world(tmp_path, BROWSE_THEN_PLAN, card=claim, files={"給苔綠細長的紙條.txt": "你的信我收到了。"})
    assert fz.build_card(rd, ws, fz.resolve(FULL, {}))["lines"] == [claim]
    (tmp_path / "n").mkdir()
    rd2, ws2 = _world(tmp_path / "n", BROWSE_THEN_PLAN, card=claim, files={"成品.txt": "只有我自己的東西。"})
    assert fz.build_card(rd2, ws2, fz.resolve(FULL, {}))["lines"] == []


def test_recheck_requires_a_look_after_the_last_product_write(tmp_path) -> None:
    claim = "你很謹慎，所以我再檢查了一次。"
    (tmp_path / "a").mkdir(), (tmp_path / "b").mkdir()
    rows_ok = BROWSE_THEN_PLAN                                                    # 最後是 ws_list
    rows_bad = BROWSE_THEN_PLAN[:-1]                                              # 最後一步是寫成品
    rd, ws = _world(tmp_path / "a", rows_ok, card=claim)
    assert fz.build_card(rd, ws, fz.resolve(FULL, {}))["lines"] == [claim]
    rd2, ws2 = _world(tmp_path / "b", rows_bad, card=claim)
    assert fz.build_card(rd2, ws2, fz.resolve(FULL, {}))["lines"] == []


def test_place_aliases_resolve_to_the_real_place(tmp_path) -> None:
    rows = STAGE1 + [_row(3, "ws_read", "信.md"), _row(4, "ws_read", "地上/長桌廣場/土堆/小陶印.txt"),
                     _row(5, "ws_write", "PLAN.md")]
    rd, ws = _world(tmp_path, rows, card="你愛摸東西，所以我翻了土堆。\n你愛熱鬧，所以我去了長桌。\n你愛安靜，所以我去了閘門。")
    res = fz.build_card(rd, ws, fz.resolve(FULL, {}))
    assert [x[:6] for x in res["lines"]] == ["你愛摸東西，", "你愛熱鬧，所"]
    assert res["dropped"][0]["why"] == "ungrounded:閘門"


# ---------------------------------------------------------------------------
# 串起來：twinagent／檔案庫／撤回
# ---------------------------------------------------------------------------

def test_not_artifacts_include_the_card_in_both_modules_and_job_carries_fortune() -> None:
    assert fz.CARD_FILE in twinagent.NOT_ARTIFACTS and twinagent.NOT_ARTIFACTS == gg.NOT_ARTIFACTS
    cfg = twinagent.AgentConfig(work_root=pathlib.Path("/x"), events_path=None, model="m", endpoint="e")
    job = twinagent.job_for("sub-1", {"need": "n", **FULL}, "", cfg)
    assert job.fortune == FULL and "INFP" in job.traits


def test_fortune_is_off_chain_in_the_vault_and_gone_after_erasure() -> None:
    assert "fortune" in twinvault.TWIN_OFF_CHAIN_KEYS and "fortune" not in twinvault.TWIN_ON_CHAIN_KEYS


def test_build_twin_carries_fortune_only_for_the_real_run_path() -> None:
    res = {"twin_id": "tw-x", "summary": {"requests_seen": 3, "run_id": "R", "tier": "C", "stop_reason": "visible_pass"},
           "outputs": {"decision": "d", "reason": "r", "artifacts": [{"name": "a.md", "text": "x"}], "has_plan": True},
           "fortune": {**fz.twin_view(fz.resolve(FULL, {}), {"first_line": "INFP", "lines": ["你，所以我寫了計畫。"]}),
                       "dropped_n": 1, "places": []}}
    tw = twinagent.build_twin(res, model="m", fallback=lambda c: {})
    assert tw["fortune"]["lines"] == ["你，所以我寫了計畫。"] and "dropped_n" not in tw["fortune"]
    assert "element" not in tw["fortune"]
    assert "fortune" not in twinagent.build_twin({**res, "outputs": {"has_plan": False}}, model="m", fallback=lambda c: {})


# ---------------------------------------------------------------------------
# 旁註與電視契約
# ---------------------------------------------------------------------------

def _fort_row(**kw):
    r = {"schema": sc.SCHEMA, "type": "twin_fortune", "ts_ms": 2000, "cell_id": "tw-x", "run_id": "R1",
         "phase": "card", "attempt": 1, "mbti": "INFP", "mbti_source": "ai", "element": "水", "blood": "O",
         "lines": ["你偏安靜，所以我先去了草稿角。"]}
    r.update(kw)
    return r


def test_sidecar_and_tv_enumerations_match_fortune_module() -> None:
    assert sc.FORTUNE_MBTI == tv.FORTUNE_MBTI == fz.MBTI_TYPES
    assert sc.FORTUNE_BLOODS == tv.FORTUNE_BLOODS == fz.BLOODS
    assert sc.FORTUNE_ELEMENTS == tv.FORTUNE_ELEMENTS == tuple(sorted(set(fz.ELEMENT_OF.values()), key="火土風水".index))
    assert sc.FORTUNE_SOURCES == tv.FORTUNE_SOURCES == fz.MBTI_SOURCES
    assert sc.FORTUNE_MAX_LINES == tv.FORTUNE_MAX_LINES == fz.MAX_CARD_LINES
    assert sc.FORTUNE_LINE_MAX == tv.FORTUNE_LINE_MAX == fz.MAX_CARD_LINE_CHARS
    assert "twin_fortune" in sc.TYPES and "twin_fortune" in tv.EMITTED


@pytest.mark.parametrize("field,value", [
    ("phase", "later"), ("attempt", 0), ("mbti", "XXXX"), ("mbti_source", "me"), ("element", "木"),
    ("blood", "C"), ("mbti_source", None), ("lines", ["a", "b", "c", "d"]), ("lines", ["字" * 61]),
    ("lines", [""]), ("lines", "x"), ("lines", ["我交出了 star_notes.md。"]),
])
def test_sidecar_validate_twin_fortune_has_teeth(field, value) -> None:
    assert sc.validate([_fort_row()]) == [], "正控制"
    assert sc.validate([_fort_row(**{field: value})]), (field, value)
    assert sc.validate([_fort_row(phase="way", lines=["不該有"])]), "way 拍不帶句子"
    assert sc.validate([_fort_row(phase="way", lines=[], mbti=None, mbti_source=None, element=None, blood=None)]) == []


def _lc(task_kind="practical", arm="RUN-ON"):
    return [{"schema": lifecycle.SCHEMA, "type": "run_started", "ts_ms": 1000, "run_id": "R1",
             "task_id": "twin:tw-x", "arm": arm, "attempt_limit": 1,
             "caller": {"cell_id": "tw-x", "resident": "x", "stratum": "twin", "task_kind": task_kind}}]


def test_folder_turns_twin_fortune_into_a_tv_event_and_tv_contract_accepts_it() -> None:
    fold = le.Folder(verify_url=None, mode=tv.MODE_LIVE)
    out = []
    for ev in _lc() + [_fort_row(phase="way", lines=[]), _fort_row()]:
        out += fold.feed(ev)
    fs = [e for e in out if e["type"] == "twin_fortune"]
    assert [e["phase"] for e in fs] == ["way", "card"], (out, fold.dropped)
    e = fs[1]
    assert (e["arm"], e["task_id"], e["mbti"], e["element"], e["blood"], e["mbti_source"]) == ("ON", "tw-x", "INFP", "水", "O", "ai")
    assert "zodiac" not in e and "path" not in e
    assert not [b for b in tv.validate(out, require_settled=False) if "twin_fortune" in b], tv.validate(out, require_settled=False)


def test_folder_drops_twin_fortune_for_a_code_cell_an_off_arm_and_a_bad_shape() -> None:
    for lc, row in ((_lc(task_kind="code"), _fort_row()), (_lc(arm="RUN-OFF"), _fort_row()),
                    (_lc(), _fort_row(mbti="XXXX")), (_lc(), _fort_row(cell_id="other"))):
        fold = le.Folder(verify_url=None, mode=tv.MODE_LIVE)
        out = []
        for ev in lc + [row]:
            out += fold.feed(ev)
        assert not [e for e in out if e["type"] == "twin_fortune"], row
        assert fold.dropped


@pytest.mark.parametrize("field,value", [
    ("phase", "x"), ("attempt", True), ("mbti", "ZZZZ"), ("element", "木"), ("blood", "C"), ("arm", "OFF"),
    ("lines", ["a"] * 4), ("zodiac", "雙魚"), ("path", "a.md"), ("text", "x"),
])
def test_tv_contract_twin_fortune_has_teeth(field, value) -> None:
    base = {"type": "twin_fortune", "ts": "2026-10-02T00:00:00Z", "task_id": "tw-x", "mode": "live", "arm": "ON",
            "phase": "card", "attempt": 1, "mbti": "INFP", "mbti_source": "ai", "element": "水", "blood": "O",
            "lines": ["你，所以我先去了草稿角。"]}
    assert not [b for b in tv.validate([base], require_settled=False) if "twin_fortune" in b]
    assert [b for b in tv.validate([dict(base, **{field: value})], require_settled=False) if "twin_fortune" in b], (field, value)


def test_sidecar_merge_puts_fortune_inside_the_run() -> None:
    lc = _lc() + [{"schema": lifecycle.SCHEMA, "type": "run_ended", "ts_ms": 9000, "run_id": "R1"}]
    r = _fort_row(ts_ms=5000)
    assert [e["type"] for e in sc.merge(lc, [r])] == ["run_started", "twin_fortune", "run_ended"]


def test_emit_writes_enumerations_only_through_gate_meta_and_event_file(tmp_path) -> None:
    rd = tmp_path / "rd"
    rd.mkdir()
    events, side = tmp_path / "lc.jsonl", tmp_path / "lc.sidecar.jsonl"
    events.write_text(json.dumps({"type": "run_started", "task_id": "twin:tw-x", "arm": "RUN-ON", "run_id": "R9"}) + "\n"
                      + json.dumps({"type": "attempt_started", "run_id": "R9"}) + "\n", encoding="utf-8")
    (rd / gg.GATE_META_NAME).write_text(json.dumps({"events_path": str(events), "sidecar_path": str(side),
                                                    "task_id": "twin:tw-x", "cell_id": "tw-x"}), encoding="utf-8")
    f = fz.resolve(FULL, {})
    assert fz.emit(rd, "way", f) is True
    assert fz.emit(rd, "card", f, ["你，所以我先去了草稿角。"]) is True
    rows = sc.read(side)
    assert [r["phase"] for r in rows] == ["way", "card"] and rows[0]["lines"] == []
    assert rows[1]["run_id"] == "R9" and rows[1]["attempt"] == 1 and rows[1]["element"] == "水"
    assert sc.validate(rows) == []
    blob = json.dumps(rows, ensure_ascii=False)
    assert "雙魚" not in blob, "旁註不帶星座名（只帶元素）"
    # 沒有 gate_meta ⇒ 不寫、不炸
    assert fz.emit(tmp_path / "nowhere", "way", f) is False


def test_cli_card_writes_card_json_and_sidecar_row(tmp_path) -> None:
    rd, ws = _world(tmp_path, BROWSE_THEN_PLAN, card="你偏安靜，所以我先去了草稿角。\n你很好，所以我去了投遞口。")
    (rd / fz.FINAL_NAME).write_text(json.dumps(fz.resolve(FULL, {})), encoding="utf-8")
    events, side = tmp_path / "lc.jsonl", tmp_path / "lc.sidecar.jsonl"
    events.write_text(json.dumps({"type": "run_started", "task_id": "twin:tw-x", "arm": "RUN-ON", "run_id": "R9"}) + "\n"
                      + json.dumps({"type": "attempt_started", "run_id": "R9"}) + "\n", encoding="utf-8")
    (rd / gg.GATE_META_NAME).write_text(json.dumps({"events_path": str(events), "sidecar_path": str(side),
                                                    "task_id": "twin:tw-x", "cell_id": "tw-x"}), encoding="utf-8")
    r = subprocess.run([sys.executable, str(TWIN / "fortune.py"), "card", str(ws), str(rd)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    rows = sc.read(side)
    assert [x["phase"] for x in rows] == ["card"] and rows[0]["lines"] == ["你偏安靜，所以我先去了草稿角。"]
    assert (rd / fz.CARD_JSON_NAME).is_file()


# ---------------------------------------------------------------------------
# 拍立得：印命盤那一行＋命盤卡一句
# ---------------------------------------------------------------------------

def test_polaroid_sentence_keeps_only_the_what_i_did_part() -> None:
    assert fz.polaroid_sentence("你偏安靜，所以我先去了草稿角。") == "我先去了草稿角"
    assert fz.polaroid_sentence("沒有那個形狀") == "沒有那個形狀"


def test_polaroid_draws_the_fortune_line_and_leaves_it_out_when_not_given() -> None:
    from ops.exhibit.twin import polaroid as pl
    ok, why = pl.available()
    if not ok:
        pytest.skip(why)
    base = dict(decision="我要整理一份清單", cast_id="c05", date_str="2026-10-02", receipt_short="a1b2c3d4", originals=[])
    png0, m0 = pl.compose(**base)
    png1, m1 = pl.compose(**base, fortune_line=fz.first_line(FULL), fortune_sentence="我先去了草稿角")
    assert m0["fortune_drawn"] is False and m1["fortune_drawn"] is True and png0 != png1
    assert m1["fortune_chars"] > len(fz.first_line(FULL))          # 命盤那一行＋一句
    # 逐字抄了觀眾原文的那一句不畫（命盤那一行照畫）
    leak = "我先去了草稿角把散在桌上的收據排好"
    _p, m2 = pl.compose(**{**base, "originals": [leak]}, fortune_line=fz.first_line(FULL), fortune_sentence=leak)
    assert m2["fortune_drawn"] is True and m2["fortune_chars"] == len(fz.first_line(FULL))
    # 版面放不下（命盤那一行長到出框）時被截成「…」而不是壓到別的字：compose 沒有丟 PolaroidError
    _p, m3 = pl.compose(**base, fortune_line=fz.first_line(FULL), fortune_sentence="我" + "很用心地做了很多事" * 10)
    assert m3["fortune_drawn"] is True


def test_publish_payload_carries_fortune_enumerations_and_lines_only() -> None:
    """`twinlink.publish` 組的 payload：fortune ＝ {mbti, mbti_source, zodiac, blood, lines}，沒有別的鍵。"""
    src = (TWIN / "twinlink.py").read_text(encoding="utf-8")
    i = src.index('payload["fortune"] = {')
    blk = src[i:i + 400]
    assert all(k in blk for k in ('"mbti"', '"mbti_source"', '"zodiac"', '"blood"', '"lines"'))
    assert "first_line" not in blk and "element" not in blk


def test_enclosed_run_forwards_twin_fortune_rows_from_the_run_dir_part_file(tmp_path) -> None:
    """圍牆裡 `fortune.emit` 只寫得到 run-dir 的 part 檔；主機側 EventForwarder 驗過形狀才轉（別格、壞形狀、別型別不轉）。"""
    from ops.exhibit.twin import twinenclose
    caller = {"cell_id": "tw-x", "resident": "X", "task_kind": "practical"}
    part, gpart, dst = tmp_path / "part.jsonl", tmp_path / "gpart.jsonl", tmp_path / "live.jsonl"
    part.write_text("", encoding="utf-8")
    good = _fort_row(ts_ms=5)
    rows = [good, dict(good, cell_id="tw-9"), dict(good, mbti="XXXX"), dict(good, type="twin_say"),
            dict(good, phase="way", lines=["不該有"]), dict(good, phase="way", lines=[])]
    gpart.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    f = twinenclose.EventForwarder(part, dst, task_id="twin:tw-x", caller=caller, gate_src=gpart,
                                   gate_dst=sc.sidecar_path(dst))
    f._pump()
    out = sc.read(sc.sidecar_path(dst))
    assert [(r["type"], r["phase"]) for r in out] == [("twin_fortune", "card"), ("twin_fortune", "way")]
    assert all(r["cell_id"] == "tw-x" for r in out) and f.gate_forwarded == 2
