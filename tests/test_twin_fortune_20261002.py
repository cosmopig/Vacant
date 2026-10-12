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
    # P13：命盤是 AI 的判決、觀眾改不了——沒有 self 這條路（舊卡帶 self 也一律當 ai）
    assert fz.normalize({"mbti": "INFP", "mbti_source": "self"})["mbti_source"] == "ai"
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
    assert "INFP（觀眾的 AI 替他占卜出來的）" in given and "星座：雙魚" in given and "血型：O" in given
    none = "\n".join(fz.traits_lines(fz.normalize(None)))
    assert "MBTI：沒有給（請你依特質猜" in none
    assert "星座：沒有給（不要猜" in none and "血型：沒有給（不要猜" in none
    assert "觀眾自己選的" not in "\n".join(fz.traits_lines({"mbti": "ENFP", "mbti_source": "self"}))


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
        assert a == a2 and a.startswith("\n\n") and "命盤卡" not in a
        n += 1
    assert n == 16 * 5 * 5
    # 只有星座、只有血型也有（不靠 MBTI）
    assert T.WAY_ELEMENT["水"] in fz.way_text({"mbti": None, "zodiac": "雙魚", "blood": None})
    assert T.WAY_BLOOD["AB"] in fz.way_text({"mbti": None, "zodiac": None, "blood": "AB"})


def test_no_fortune_means_empty_way_and_identical_stage2_argv() -> None:
    assert fz.way_text({"mbti": None, "zodiac": None, "blood": None}) == ""
    assert fz.reminder({"blood": "O"}) == ""                       # 第二版：段 2 不再有任何命盤卡的要求
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
    sh = "\n".join(ln for ln in (TWIN / "twin_agent.sh").read_text(encoding="utf-8").splitlines()
                   if not ln.lstrip().startswith("#"))
    assert 'fortune.py" way "$RUN_DIR"' in sh and 'SYS="$SYS$WAY"' in sh
    assert 'fortune.py" announce "$RUN_DIR"' in sh and 'fortune.py" card "$(pwd)" "$RUN_DIR"' in sh
    # 順序：寫信（一通模型）→ 關卡 → way → runwatch（pi 段 2）→ card → prepare
    assert sh.index("twin_letter.py") < sh.index("twin_letter_guard.py") < sh.index('SYS="$SYS$WAY"') < sh.index("runwatch") \
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
            f"printf '%s' \"$SP\" > {rd}/sys2.txt; printf '%s' \"$LAST\" > {rd}/msg2.txt\n",
            encoding="utf-8")
        fake.chmod(0o755)
        fake_letter = base / "letter.py"            # P13：段 1 是 twin_letter.py（一通模型呼叫）；這裡換成寫死的替身
        fake_letter.write_text("import pathlib, sys\npathlib.Path(sys.argv[2], '信.md').write_text("
                               "'這個人手慢。\\n\\n命盤\\nMBTI：INFP\\nE/I：話少\\n', encoding='utf-8')\n", encoding="utf-8")
        env = {**os.environ, "VACANT_RUN_PROXY": "http://127.0.0.1:1", "VACANT_TWIN_PI": str(fake),
               "VACANT_TWIN_PY": sys.executable, "VACANT_TWIN_LETTER": str(fake_letter)}
        r = subprocess.run(["bash", str(TWIN / "twin_agent.sh"), "S1", "M1", str(rd), "BASE-SYS", "MSG"],
                           cwd=ws, env=env, capture_output=True, text=True, timeout=60)
        assert r.returncode == 0, r.stderr
        sys2 = (rd / "sys2.txt").read_text(encoding="utf-8")
        msg2 = (rd / "msg2.txt").read_text(encoding="utf-8")
        if want_way:
            assert sys2.startswith("BASE-SYS\n\n" + T.WAY_INTRO) and (T.WAY_JP["J"] in sys2 or T.WAY_JP["P"] in sys2)
            assert "命盤卡" not in sys2 and msg2 == "MSG"
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
        f"printf '%s' \"$SP\" > {rd}/sys2.txt; printf '%s' \"$LAST\" > {rd}/msg2.txt\n",
        encoding="utf-8")
    fake.chmod(0o755)
    fake_letter = tmp_path / "letter.py"
    fake_letter.write_text("import pathlib, sys\npathlib.Path(sys.argv[2], '信.md').write_text('這個人手慢。\\n', encoding='utf-8')\n",
                           encoding="utf-8")
    env = {**os.environ, "VACANT_RUN_PROXY": "http://127.0.0.1:1", "VACANT_TWIN_PI": str(fake),
           "VACANT_TWIN_PY": sys.executable, "VACANT_TWIN_LETTER": str(fake_letter)}
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
    tmp_path.mkdir(parents=True, exist_ok=True)
    rd, ws = tmp_path / "rd", tmp_path / "ws"
    rd.mkdir(), ws.mkdir()
    _steps(rd, rows)
    from ops.exhibit.twin import twinground
    for rel in twinground.pool():                      # 這一跑地上有的東西（stage2_in 備份；內容不重要）
        q = rd / "stage2_in" / "地上" / rel
        q.parent.mkdir(parents=True, exist_ok=True)
        q.write_text("x", encoding="utf-8")
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


LETTER_FINAL = ("這個人手慢。\n\n命盤\nMBTI：你是 INFP（你自己選的）\nE/I：話不多，待在角落看人。\nS/N：愛想像還沒成形的東西。\n"
                "T/F：先想到的是別人的心情。\nJ/P：在計畫的框架中掙扎，卻往往被隨興的逃避行為帶離軌道。\n星座：雙魚（水象）。像水。\n")


_REC_DEFAULT = "# 試的紀錄\n" + "第一步，我走過去把東西拿起來看。第二步，它掉了，我撿起來接著做。" * 2 + "\n"


def _card(tmp, rows, letter=LETTER_FINAL, f=None, files=None, traits="", attempts=1, norecord=False):
    pathlib.Path(tmp).mkdir(parents=True, exist_ok=True)
    if not norecord:                       # P13 第二輪：沒有「試的紀錄」就沒有第 3、4 行；預設給一份夠長的
        files = {fz.RECORD_FILE: _REC_DEFAULT, **(files or {})}
    rd, ws = _world(pathlib.Path(tmp), rows, card=None, files=files)
    (rd / "letter_final.md").write_text(letter, encoding="utf-8")
    (rd / "run_RUN-ON.json").write_text(json.dumps({"attempts": [{}] * attempts}), encoding="utf-8")
    return fz.build_card(rd, ws, f or fz.resolve(FULL, {}), traits), rd, ws


PLAN_TXT = "我想：想讓那顆沒有人澆過的種子長出東西\n\n為什麼是他：你……\n"
RECORD_TXT = ("# 試的紀錄\n第一步……\n第二步失敗了……\n改變：我把種子埋進兩道光交界的土裡，那裡現在有一個濕濕的小土堆。\n"
              "感想：它比我想的輕，也比我想的倔。\n")


def test_card_v3_is_four_lines_from_plan_steps_and_record_without_the_model(tmp_path) -> None:
    """P13：你的數位分身其實是…／它心裡一直想試的是…（PLAN 第一行）／它試了…（步驟紀錄）／試完它說…（試的紀錄最後的感想）。"""
    files = {"PLAN.md": PLAN_TXT, fz.RECORD_FILE: RECORD_TXT, "成品.md": "# 鬆環對照冊\n內文"}
    res, rd, ws = _card(tmp_path, BROWSE_THEN_PLAN, files=files)
    assert res["verdict"] == "你的數位分身其實是：INFP · 雙魚（水）· O 型" and res["first_line"] == "INFP · 雙魚（水）· O 型"
    assert res["want_line"] == "它心裡想：讓那顆沒有人澆過的種子長出東西"
    assert res["tried_line"] == "它試了：把種子埋進兩道光交界的土裡，那裡現在有一個濕濕的小土堆", "第 3 行＝紀錄裡的改變那一句（第三人稱），不是路線"
    assert res["said_line"] == "試完它說：它比我想的輕，也比我想的倔"
    assert res["title"] == "鬆環對照冊", "標題取「做出來的那樣東西」，不是試的紀錄"
    # 整合（2026-10-12）：四行卡只留紀錄（lines_v3／fortune_card.json），給觀眾的 head／lines 是「像不像你」
    assert res["lines_v3"] == [res["verdict"], res["want_line"], res["tried_line"], res["said_line"]]
    assert res["head"] == fz.MIRROR_HEAD and 1 <= len(res["lines"]) <= fz.MAX_MIRROR_LINES
    assert res["tv_lines"] == [fz.strip_step(x) for x in res["lines"]], "電視字幕＝同一份習慣句（≤3）、不帶步數"
    for ln in res["lines_v3"]:
        assert ln not in res["lines"]
    assert fz.card_md(res).splitlines() == [fz.MIRROR_HEAD] + res["lines"]
    assert all(len(x) <= fz.MAX_CARD_LINE_CHARS for x in res["lines"])      # 雲端每句 ≤ 60 字
    card_json = json.loads((rd / fz.CARD_JSON_NAME).read_text(encoding="utf-8"))
    assert card_json["verdict"] == res["verdict"] and card_json["lines_v3"] == res["lines_v3"]
    assert "試的紀錄" not in "".join(res["lines"]) and res["title"] == "鬆環對照冊"
    assert (rd / fz.CARD_JSON_NAME).is_file()
    v = fz.twin_view(fz.resolve(FULL, {}), res)
    assert v["lines"] == res["lines"] and v["verdict"] == res["verdict"] and v["said_line"] == res["said_line"]


def test_card_v2_is_four_parts_built_without_the_model(tmp_path) -> None:
    rows = BROWSE_THEN_PLAN                      # 草稿角→帳本鏈；PLAN；成品.md；ws_list(.)
    res, rd, ws = _card(tmp_path, rows, files={"成品.md": "# 鬆環對照冊\n內文"})
    assert res["first_line"] == "INFP · 雙魚（水）· O 型"
    assert len(res["reading"]) <= fz.MAX_SENTENCE
    assert res["reading"].startswith("在計畫的框架中掙扎")                       # 優先挑 J/P（紀錄用，不給觀眾）
    assert res["route"] == "它先去了草稿角，再到帳本鏈，在帳本鏈交出《鬆環對照冊》"
    assert res["title"] == "鬆環對照冊"
    # 2026-10-12：解讀句與路線句只留作紀錄；給觀眾的是做事習慣（先逛兩處才寫計畫、寫完成品又列了房間）
    assert 2 <= len(res["lines"]) <= 3 and all(fz.step_of(x) for x in res["lines"])
    assert {"還沒決定要做什麼，先到處看了一圈", "交出去之前，又回頭再看了一遍"} <= set(_mirror(rows, {"成品.md": "# 鬆環對照冊\n內文"}, 0, "鬆環對照冊"))
    assert res["reading"] not in res["lines"] and res["route"] not in res["lines"]
    md = fz.card_md(res).splitlines()
    assert md == [fz.MIRROR_HEAD] + res["lines"]
    assert (rd / fz.CARD_JSON_NAME).is_file()
    v = fz.twin_view(fz.resolve(FULL, {}), res)
    assert v["lines"] == res["lines"] and v["verdict"] == res["verdict"] and v["said_line"] == res["said_line"]


def test_card_v3_a_line_without_grounds_is_absent_not_filled_with_a_canned_one(tmp_path) -> None:
    res, _, _ = _card(tmp_path / "a", BROWSE_THEN_PLAN, files={"PLAN.md": PLAN_TXT, "成品.md": "# 鬆環對照冊\n內文"})
    # 紀錄裡沒有感想、沒有改變、標題只是檔案自己的字樣 ⇒ 第 3、4 行都沒有（不補罐頭句）
    assert res["said_line"] is None and res["tried_line"] is None and res["want_line"]
    assert len(res["lines_v3"]) == 2, "四行卡（紀錄）：判決＋想，沒有第 3、4 行"
    res2, _, _ = _card(tmp_path / "b", STAGE1 + [_row(3, "ws_read", "信.md"), _row(4, "ws_write", "PLAN.md")],
                       files={"PLAN.md": PLAN_TXT, fz.RECORD_FILE: RECORD_TXT})
    assert res2["tried_line"] and "先去了" not in res2["tried_line"], "第 3 行不靠路線：步驟紀錄沒有地點也照出（來自紀錄）"
    res3, _, _ = _card(tmp_path / "c", BROWSE_THEN_PLAN, files={fz.RECORD_FILE: RECORD_TXT})
    assert res3["want_line"] is None and res3["said_line"] and res3["tried_line"], "沒有 PLAN ⇒ 沒有第 2 行"


def test_card_v3_filters_leak_time_reality_filename_and_receipt_claims() -> None:
    f = fz.resolve(FULL, {})
    tr = "他一直想把週末的時間安排得不那麼亂"
    assert fz.want_of("我想：讓週末的時間安排得不那麼亂", tr, f) is None                         # 逐字抄觀眾原文（≥8 字）
    assert fz.want_of("我想：讓種子在每天都亮的土裡長", "x", f) is None                          # 時段詞
    assert fz.want_of("我想：讓我的伴侶有一盞燈", "x", f) is None                                 # 現實詞
    assert fz.want_of("我想：看 地上/草稿角/小燈.txt 會不會亮", "x", f) == "看小燈會不會亮"      # 路徑／檔名先清成物件的名字（清完留下的空白也拿掉）
    assert fz.want_of("我想：看 notes.json 裡的字", "x", f) is None                          # 清不掉的檔名樣子照擋
    assert fz.want_of("我想：讓小燈亮了，拿到了收據", "x", f) is None                           # 自己說閘門給了結果
    assert fz.want_of("PLAN\n我想：讓那盞沒有人點過的燈亮起來", "x", f) == "讓那盞沒有人點過的燈亮起來"     # 只是標題字樣的行不算
    assert fz.want_of("我想：想讓燈被點亮。", "x", f) == "讓燈被點亮"
    assert fz.want_of("第一行：把燈點亮。", "x", f) is None, "沒有「我想：」＝沒有這一行（不拿動作句充數）"
    assert fz.said_of("感想：好像比我想的軟。", "x", f) == "好像比我想的軟"
    assert fz.said_of("感想：先\n感想：後來才明白不是風。", "x", f) == "後來才明白不是風", "取最後一個感想"
    assert fz.said_of("試完我說：嗯。", "x", f) is None          # 第四輪：一個字不是一句話，寧缺
    assert fz.said_of("沒有感想這一行", "x", f) is None
    long_ = fz.said_of("感想：" + "長" * 80, "x", f)
    assert long_ is None or len(long_) <= fz.MAX_SAID_CARD
    no_zodiac = fz.resolve(fz.normalize({"mbti": "INFP"}), {})
    assert fz.said_of("感想：像個雙魚座", "x", no_zodiac) is None                          # 沒給的星座不准出現


def test_card_v3_polaroid_prints_the_twins_own_words_else_the_want() -> None:
    both = {"said_line": "試完它說：它比我想的輕", "want_line": "它心裡一直想試的是：種一顆種子", "lines": ["x"]}
    assert fz.polaroid_pick(both) == "試完它說：它比我想的輕"
    assert fz.polaroid_pick({"want_line": "它心裡一直想試的是：種一顆種子。"}) == "它心裡一直想試的是：種一顆種子"
    assert fz.polaroid_pick({"lines": ["舊版解讀句。"]}) == "舊版解讀句" and fz.polaroid_pick(None) == ""


def test_letter_section_carries_the_abstract_want_line_and_drops_the_unsafe_one() -> None:
    sec = {"mbti": "INFP", "EI": "話不多", "want": "想靠近一件一直不敢碰的東西"}
    f = fz.resolve(fz.normalize({"mbti": "INFP"}), sec)
    text, cnt = fz.render_section(f, sec, "")
    assert "想試：想靠近一件一直不敢碰的東西" in text
    body, parsed = fz.parse_letter("信本文\n\n命盤\nMBTI：INFP\n想試：想靠近一件一直不敢碰的東西\n")
    assert parsed["want"] == "想靠近一件一直不敢碰的東西" and body == "信本文"
    bad, cnt2 = fz.render_section(f, {**sec, "want": "想把論文寫完"}, "")
    assert "想試" not in bad and {d["key"]: d["why"] for d in cnt2["dropped"]}.get("want") == "reality"
    assert "想試" not in fz.render_section(f, {"mbti": "INFP"}, "")[0], "沒有想試的鍵就不寫"
    leak, _ = fz.render_section(f, {**sec, "want": "把週末的時間安排得不那麼亂"}, "把週末的時間安排得不那麼亂")
    assert "想試" not in leak                                                              # 逐字抄特質


def test_card_v2_reading_priority_and_filters() -> None:
    f = fz.resolve(FULL, {})
    assert fz.reading_of(LETTER_FINAL, f).startswith("在計畫的框架中掙扎")
    no_jp = LETTER_FINAL.replace("J/P：在計畫的框架中掙扎，卻往往被隨興的逃避行為帶離軌道。\n", "")
    assert fz.reading_of(no_jp, f) == "先想到的是別人的心情。"                      # 其次 T/F
    only_ei = "x\n\n命盤\nMBTI：你是 INFP（你自己選的）\nE/I：話不多。\n"
    assert fz.reading_of(only_ei, f) == "話不多。"                                   # 第一個存在的行
    bad = LETTER_FINAL.replace("在計畫的框架中掙扎，卻往往被隨興的逃避行為帶離軌道。", "更傾向於與特定的伴侶建立連結。")
    assert fz.reading_of(bad, f) == "先想到的是別人的心情。"                         # 現實詞整句換下一個
    assert fz.reading_of("沒有命盤段的信", f) is None
    long_ = LETTER_FINAL.replace("在計畫的框架中掙扎，卻往往被隨興的逃避行為帶離軌道。", "在計畫的框架中掙扎，卻往往被隨興的逃避行為帶離軌道，而且每一次都假裝什麼也沒發生過似的繼續往前走。")
    assert len(fz.reading_of(long_, f)) <= fz.MAX_SENTENCE
    assert fz.reading_of(LETTER_FINAL, f, traits="在計畫的框架中掙扎，卻往往被隨興的逃避行為帶離軌道") == "先想到的是別人的心情。"   # LEAK


def test_card_v3_tried_line_comes_from_the_record_not_the_route(tmp_path) -> None:
    rows = STAGE1 + [_row(3, "ws_read", "信.md"), _row(4, "ws_read", "地上/投遞口/a.txt"), _row(5, "ws_list", "地上/捏土處"),
                     _row(8, "ws_read", "地上/帳本鏈/d.txt"), _row(11, "ws_write", "PLAN.md"), _row(13, "ws_write", "成品.md")]
    res, _, _ = _card(tmp_path, rows, files={"成品.md": "# 一件小事\n內", fz.RECORD_FILE: RECORD_TXT}, attempts=3)
    t = res["tried_line"]
    assert t.startswith("它試了：") and len(t) <= fz.MAX_CARD_LINE_CHARS
    for route in ("先去了", "再到", "做出《", "被退回", "投遞口", "帳本鏈"):
        assert route not in t, route
    assert res["places"] == ["投遞口", "捏土處", "帳本鏈"], "路線仍留在卡的紀錄裡（檔案庫），只是不上卡"


def test_card_v3_tried_line_fits_the_limit_and_falls_back_to_the_title(tmp_path) -> None:
    f = fz.resolve(FULL, {})
    r = fz.tried_of("標題\n改變：" + "那" * 60 + "\n感想：好。", "x", f)
    assert r is None, "第四輪：改變句太長又沒有句讀可截 ⇒ 不硬切半個詞；標題是名詞片語、不再當後備 ⇒ 沒有這一行"
    assert fz.tried_of("# 試的紀錄\n改變：" + "那" * 60, "x", f) is None, "標題也只是檔案字樣 ⇒ 沒有這一行"
    assert fz.tried_of("寫給誰的信\n我做了。\n", "x", f) is None, "第四輪：標題不當候選"
    assert fz.tried_of("# 試的紀錄\n我做了。\n", "x", f) is None, "檔案自己的標題字樣不是名字"
    assert fz.tried_of("", "x", f) is None


def test_card_v2_route_fits_the_line_limit_and_handles_no_title_no_place(tmp_path) -> None:
    long_title = "一個很長很長的世界裡的標題名字啊"
    r = fz.route_of(["投遞口", "長桌廣場", "畫架與長椅", "石頭閘門"], "石頭閘門", long_title, 2)
    assert len(r) <= fz.MAX_CARD_LINE_CHARS and r.startswith("它先去了投遞口")
    res, _, _ = _card(tmp_path / "a", STAGE1 + [_row(3, "ws_read", "信.md"), _row(4, "ws_write", "PLAN.md")])
    assert "route" not in res                                                        # 沒碰過任何地點：不編路線
    assert res["lines"] == []                                                        # 只寫了計畫、沒做出東西：沒有習慣句可說
    assert fz.card_md(res) == ""
    res2, _, _ = _card(tmp_path / "b", BROWSE_THEN_PLAN)                              # 沒有成品檔：標題用「一件沒有名字的小事」
    assert res2["title"] is None and "《" + fz.NO_NAME_TITLE + "》" in res2["route"]


def test_card_v3_never_reads_a_card_the_twin_wrote_and_no_fortune_means_no_card(tmp_path) -> None:
    rd, ws = _world(tmp_path / "x", BROWSE_THEN_PLAN, card="你是 P，所以我去了投遞口（亂寫的卡）")
    (rd / "letter_final.md").write_text(LETTER_FINAL, encoding="utf-8")
    res = fz.build_card(rd, ws, fz.resolve(FULL, {}))
    assert "亂寫" not in fz.card_md(res) and "投遞口" not in res["route"] and "投遞口" not in (res["tried_line"] or "")
    # 2026-10-12：習慣句只看步驟紀錄 ⇒ 沒有命盤也出卡（但沒有解讀、沒有路線）
    none = fz.build_card(rd, ws, fz.resolve(fz.normalize(None), {}))
    assert none["present"] is True and none["lines"] == res["lines"]
    assert "reading" not in none and "route" not in none


def test_card_v2_title_has_no_filename_and_is_filtered(tmp_path) -> None:
    f = fz.resolve(FULL, {})
    for i, (text, want) in enumerate((("# 鬆環對照冊\n內文", "鬆環對照冊"), ("【帳本鏈修復對照表】\n內文", "帳本鏈修復對照表"), ("版本一\n內文", None), ("補全紀錄.md\n內文", None),
                                      ("給守口人的小卡：\n內文", "給守口人的小卡"),
                                      ("一個非常非常非常非常非常長的標題超過二十個字了\n內文", None),
                                      ("替伴侶補的清單\n內文", None), ("每天早上的清單\n內文", None),
                                      ("雙魚座的清單\n內文", "雙魚座的清單"))):
        d = tmp_path / str(i)
        d.mkdir()
        (d / "成品.md").write_text(text, encoding="utf-8")
        assert fz.main_title(d, f) == want, text


def test_card_v2_title_respects_what_was_not_given_and_the_viewers_words(tmp_path) -> None:
    f2 = fz.resolve(fz.normalize({"mbti": "INFP"}), {})
    d = tmp_path / "z"
    d.mkdir()
    (d / "成品.md").write_text("雙魚座的清單\n", encoding="utf-8")
    assert fz.main_title(d, f2) is None                                     # 沒給星座不准出現
    (d / "成品.md").write_text("把心情放回原處才覺得安心\n", encoding="utf-8")
    assert fz.main_title(d, f2, traits="他總把心情放回原處才覺得安心") is None   # 逐字抄觀眾原文


def test_reality_words_are_dropped_from_the_letter_section() -> None:
    sec = {"mbti": "INFP", "EI": "更傾向於與特定的伴侶建立深層連結", "SN": "專注於當下的細節", "TF": "在意家人的安危",
           "JP": "把論文拖到最後", "zodiac": "水象", "blood": "穩穩的"}
    f = fz.resolve(fz.normalize({"mbti": "INFP", "zodiac": "雙魚", "blood": "O"}), sec)
    text, cnt = fz.render_section(f, sec, "")
    why = {d["key"]: d["why"] for d in cnt["dropped"]}
    assert why == {"EI": "reality", "TF": "reality", "JP": "reality"}, why
    assert "伴侶" not in text and "家人" not in text and "論文" not in text and "專注於當下的細節" in text
    for w in ("伴侶", "家人", "工作", "學校", "論文", "寵物"):
        assert w in fz.REALITY_WORDS


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


def test_polaroid_hints_survive_the_vault_seal_p12_regression() -> None:
    """P12 端到端量到：twinagent 輸出 polaroid_hints，但白名單沒收 ⇒ 封存時被丟、拍立得永遠沒有地點／物件的提示。"""
    assert "polaroid_hints" in twinvault.TWIN_OFF_CHAIN_KEYS and "polaroid_hints" not in twinvault.TWIN_ON_CHAIN_KEYS


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
         "phase": "card", "attempt": 1, "mbti": "INFP", "mbti_source": "ai", "zodiac": "雙魚", "element": "水",
         "blood": "O", "lines": ["你偏安靜，所以我先去了草稿角。"]}
    r.update(kw)
    return r


def test_sidecar_and_tv_enumerations_match_fortune_module() -> None:
    assert sc.FORTUNE_MBTI == tv.FORTUNE_MBTI == fz.MBTI_TYPES
    assert sc.FORTUNE_ZODIACS == tv.FORTUNE_ZODIACS == fz.ZODIACS
    assert tv._ELEMENT_OF_ZODIAC == fz.ELEMENT_OF
    assert sc.FORTUNE_BLOODS == tv.FORTUNE_BLOODS == fz.BLOODS
    assert sc.FORTUNE_ELEMENTS == tv.FORTUNE_ELEMENTS == tuple(sorted(set(fz.ELEMENT_OF.values()), key="火土風水".index))
    assert sc.FORTUNE_SOURCES == tv.FORTUNE_SOURCES == fz.MBTI_SOURCES
    assert sc.FORTUNE_MAX_LINES == tv.FORTUNE_MAX_LINES == fz.MAX_CARD_LINES
    assert sc.FORTUNE_LINE_MAX == tv.FORTUNE_LINE_MAX == fz.MAX_CARD_LINE_CHARS
    assert "twin_fortune" in sc.TYPES and "twin_fortune" in tv.EMITTED


@pytest.mark.parametrize("field,value", [
    ("phase", "later"), ("attempt", 0), ("mbti", "XXXX"), ("mbti_source", "me"), ("element", "木"),
    ("blood", "C"), ("zodiac", "火星"), ("zodiac", None), ("element", None), ("mbti_source", None), ("lines", ["a", "b", "c", "d"]), ("lines", ["字" * 61]),
    ("lines", [""]), ("lines", "x"), ("lines", ["我交出了 star_notes.md。"]),
])
def test_sidecar_validate_twin_fortune_has_teeth(field, value) -> None:
    assert sc.validate([_fort_row()]) == [], "正控制"
    assert sc.validate([_fort_row(**{field: value})]), (field, value)
    assert sc.validate([_fort_row(phase="way", lines=["不該有"])]), "way 拍不帶句子"
    assert sc.validate([_fort_row(phase="way", lines=[], mbti=None, mbti_source=None, zodiac=None, element=None, blood=None)]) == []


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
    assert (e["arm"], e["task_id"], e["mbti"], e["zodiac"], e["element"], e["blood"], e["mbti_source"]) == (
        "ON", "tw-x", "INFP", "雙魚", "水", "O", "ai")
    assert "path" not in e
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
    ("lines", ["a"] * 4), ("zodiac", "火星"), ("zodiac", None), ("element", "火"), ("path", "a.md"), ("text", "x"),
])
def test_tv_contract_twin_fortune_has_teeth(field, value) -> None:
    base = {"type": "twin_fortune", "ts": "2026-10-02T00:00:00Z", "task_id": "tw-x", "mode": "live", "arm": "ON",
            "phase": "card", "attempt": 1, "mbti": "INFP", "mbti_source": "ai", "zodiac": "雙魚", "element": "水", "blood": "O",
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
    assert rows[1]["run_id"] == "R9" and rows[1]["attempt"] == 1 and rows[1]["element"] == "水" and rows[1]["zodiac"] == "雙魚"
    assert sc.validate(rows) == []
    # 沒給星座 ⇒ zodiac 與 element 都是 null（不猜）
    assert fz.emit(rd, "way", fz.resolve(fz.normalize({"mbti": "ENTP"}), {})) is True
    last = sc.read(side)[-1]
    assert last["zodiac"] is None and last["element"] is None and sc.validate([last]) == []
    # 沒有 gate_meta ⇒ 不寫、不炸
    assert fz.emit(tmp_path / "nowhere", "way", f) is False


def test_cli_card_writes_card_json_and_sidecar_row(tmp_path) -> None:
    rd, ws = _world(tmp_path, BROWSE_THEN_PLAN, card=None, files={"成品.md": "# 鬆環對照冊\n內文", "PLAN.md": PLAN_TXT, fz.RECORD_FILE: RECORD_TXT})
    (rd / "letter_final.md").write_text(LETTER_FINAL, encoding="utf-8")
    (rd / fz.FINAL_NAME).write_text(json.dumps(fz.resolve(FULL, {})), encoding="utf-8")
    events, side = tmp_path / "lc.jsonl", tmp_path / "lc.sidecar.jsonl"
    events.write_text(json.dumps({"type": "run_started", "task_id": "twin:tw-x", "arm": "RUN-ON", "run_id": "R9"}) + "\n"
                      + json.dumps({"type": "attempt_started", "run_id": "R9"}) + "\n", encoding="utf-8")
    (rd / gg.GATE_META_NAME).write_text(json.dumps({"events_path": str(events), "sidecar_path": str(side),
                                                    "task_id": "twin:tw-x", "cell_id": "tw-x"}), encoding="utf-8")
    r = subprocess.run([sys.executable, str(TWIN / "fortune.py"), "card", str(ws), str(rd)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    rows = sc.read(side)
    assert [x["phase"] for x in rows] == ["card"] and len(rows[0]["lines"]) <= 3 and rows[0]["lines"]
    assert rows[0]["lines"] and not any("（第" in x for x in rows[0]["lines"]) and sc.validate(rows) == []     # 電視字幕＝像不像你的習慣句（≤3）
    assert not any(x.startswith(("它心裡想：", "它試了：", "試完它說：", fz.VERDICT_PREFIX)) for x in rows[0]["lines"]), "四行卡不上電視"
    assert (rd / fz.CARD_JSON_NAME).is_file()


def test_polaroid_prints_the_reading_sentence() -> None:
    assert fz.polaroid_sentence("在計畫的框架中掙扎，卻被帶離軌道。") == "在計畫的框架中掙扎，卻被帶離軌道"


# ---------------------------------------------------------------------------
# 拍立得：印命盤那一行＋命盤卡一句
# ---------------------------------------------------------------------------

def test_polaroid_draws_the_fortune_line_and_leaves_it_out_when_not_given() -> None:
    from ops.exhibit.twin import polaroid as pl
    ok, why = pl.available()
    if not ok:
        pytest.skip(why)
    base = dict(decision="我要整理一份清單", cast_id="c05", date_str="2026-10-02", receipt_short="a1b2c3d4", originals=[])
    png0, m0 = pl.compose(**base)
    png1, m1 = pl.compose(**base, fortune_line=fz.first_line(FULL), fortune_sentence="我先去了草稿角")
    assert m0["fortune_drawn"] is False and m1["fortune_drawn"] is True and png0 != png1
    assert m1["fortune_chars"] == len(fz.first_line(FULL))         # P12：命盤那一行只留命盤；解讀句改印在主字那一行
    assert m1["caption_source"] == "fortune_sentence" and m0["caption_source"] == "decision"
    # 逐字抄了觀眾原文的那一句不畫（命盤那一行照畫）
    leak = "我先去了草稿角把散在桌上的收據排好"
    _p, m2 = pl.compose(**{**base, "originals": [leak]}, fortune_line=fz.first_line(FULL), fortune_sentence=leak)
    assert m2["fortune_drawn"] is True and m2["fortune_chars"] == len(fz.first_line(FULL))
    assert m2["caption_source"] == "decision"                           # 解讀句逐字抄了原文 ⇒ 退回決定句
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


def test_twin_fortune_zodiac_must_be_one_of_twelve_and_match_its_element() -> None:
    assert sc.validate([_fort_row(zodiac="火星")])                                                   # 旁註這一層也擋亂星座名
    assert tv.fortune_event_problems({**_fort_row(zodiac="火星"), "type": "twin_fortune"}, 1)       # 亂星座名被擋
    assert tv.fortune_event_problems({**_fort_row(zodiac="雙魚", element="火"), "type": "twin_fortune"}, 1)   # 與元素對不上
    assert tv.fortune_event_problems({**_fort_row(zodiac=None, element="水"), "type": "twin_fortune"}, 1)
    assert not tv.fortune_event_problems({**_fort_row(zodiac=None, element=None), "type": "twin_fortune"}, 1)   # 沒給＝null
    assert not tv.fortune_event_problems({**_fort_row(), "type": "twin_fortune"}, 1)


def test_p12_single_place_route_and_short_or_resident_titles(tmp_path) -> None:
    assert fz.route_of(["草稿角"], "草稿角", "寫給誰的信", 0) == "它在草稿角交出《寫給誰的信》"
    assert fz.route_of(["草稿角"], None, "寫給誰的信", 1) == "它在草稿角交出《寫給誰的信》；中途被退回 1 次，改了 1 次"
    assert fz.route_of(["草稿角", "畫架與長椅"], "畫架與長椅", "寫給誰的信", 0).startswith("它先去了草稿角，再到畫架與長椅")
    f = fz.resolve(FULL, {})
    assert fz.title_of({"a.md": "# 小事\n內"}, f) is None                     # < 3 字
    assert fz.title_of({"a.md": "# 苔綠細長\n內"}, f) is None                 # 居民外形名
    assert fz.title_of({"a.md": "# 灰藍小\n內"}, f) is None
    assert fz.title_of({"a.md": "# 阿水\n內"}, f, letter_text="阿水：\n你好") is None      # 信裡的稱呼
    assert fz.title_of({"a.md": "# 帳本鏈維護記錄\n內"}, f) == "帳本鏈維護記錄"


# ---------------------------------------------------------------------------
# 2026-10-12「像不像你」：給觀眾的句子＝這一跑真的做過的做事習慣（不是命盤解讀、不是世界裡的路線）
# ---------------------------------------------------------------------------

def _mirror(rows, files=None, retries=0, title=None):
    """所有「成立的習慣」句子（不含步數）——挑哪三句是 `mirror_pick` 的事（稀有度），這裡驗的是各句的判準。"""
    ev = fz.Evidence(rows, None)
    ev.files = dict(files or {})
    return [c["text"] for c in fz.mirror_candidates(ev, retries, title)]


def _picked(rows, files=None, retries=0, title=None):
    return fz.mirror_lines(rows, files or {}, retries, title)


def test_mirror_start_follows_the_step_order() -> None:
    assert "還沒決定要做什麼，先到處看了一圈" in _mirror(BROWSE_THEN_PLAN)           # 兩個地點後才寫計畫
    one = STAGE1 + [_row(3, "ws_read", "信.md"), _row(4, "ws_read", "地上/草稿角/紙團_乙.txt"),
                    _row(5, "ws_write", "PLAN.md"), _row(6, "ws_write", "成品.md")]
    assert "先去看了一眼，才決定要做什麼" in _mirror(one)                           # 只看了一處
    assert "先把要做的事寫下來，才開始動手" in _mirror(PLAN_THEN_BROWSE)
    direct = STAGE1 + [_row(3, "ws_read", "信.md"), _row(4, "ws_read", "地上/草稿角/a.txt"), _row(5, "ws_write", "成品.md")]
    assert "沒寫計畫，直接就動手做了" in _mirror(direct)
    # 負控制：只寫了計畫、什麼都沒看也沒做 ⇒ 沒有任何一句（不補）
    assert _picked(STAGE1 + [_row(3, "ws_read", "信.md"), _row(4, "ws_write", "PLAN.md")]) == []


def test_mirror_habits_appear_only_with_their_step() -> None:
    twice = PLAN_THEN_BROWSE + [_row(9, "ws_write", "PLAN.md")]
    assert "做到一半改了主意，把計畫重寫了一遍" in _mirror(twice)
    assert "做到一半改了主意，把計畫重寫了一遍" not in _mirror(PLAN_THEN_BROWSE)       # 負控制：PLAN 只寫過一次
    thrice = twice + [_row(10, "ws_write", "PLAN.md")]
    assert "計畫寫了又改，前後改了 2 次" in _mirror(thrice)
    two = {"a.md": "版本一\n…", "b.md": "版本二\n…"}
    assert "拿不定主意，乾脆做了兩個版本" in _mirror(PLAN_THEN_BROWSE, files=two)
    assert "拿不定主意，乾脆做了兩個版本" not in _mirror(PLAN_THEN_BROWSE, files={"a.md": "版本一"})
    assert "做好的東西，特地寫明了要留給誰" in _mirror(PLAN_THEN_BROWSE, files={"給守口人.md": "x"})
    assert "做好的東西，寫明了收在哪裡" in _mirror(PLAN_THEN_BROWSE, files={"a.md": "收在長桌下"})
    many = STAGE1 + [_row(3, "ws_read", "信.md")] + [_row(4 + i, "ws_read", f"地上/草稿角/{i}.txt") for i in range(6)] \
        + [_row(20, "ws_write", "PLAN.md"), _row(21, "ws_write", "成品.md")]
    assert "前前後後翻了 6 樣東西" in _mirror(many)
    assert any(x.startswith("沒看幾樣東西") for x in _mirror(PLAN_THEN_BROWSE))
    assert not any(x.startswith("沒看幾樣東西") for x in _mirror(many))               # 負控制
    assert "被退回 2 次，每一次都回去改" in _mirror(PLAN_THEN_BROWSE, retries=2)
    assert not any("退回" in x for x in _mirror(PLAN_THEN_BROWSE, retries=0))


def test_mirror_is_at_most_three_lines_with_steps_and_a_real_habit() -> None:
    rows = BROWSE_THEN_PLAN + [_row(11, "ws_write", "PLAN.md")]
    ls = _picked(rows, files={"a.md": "版本一", "b.md": "版本二"}, retries=1, title="點數單")
    assert 2 <= len(ls) <= fz.MAX_MIRROR_LINES and all(fz.step_of(x) for x in ls)
    plain = [fz.strip_step(x) for x in ls]
    assert any(not x.startswith(("還沒決定要做什麼", "先去看了一眼", "先把要做的事寫下來", "沒寫計畫", "第一個動手翻的", "最後做出來的是"))
               for x in plain), "至少一句不是「開頭方式」或「最後做出來的是」"
    assert plain[-1].startswith("最後做出來的是") or all(not x.startswith("最後做出來的是") for x in plain)
    # 「改主意」最稀有 ⇒ 一定被挑中
    assert "做到一半改了主意，把計畫重寫了一遍" in plain


def test_mirror_lines_never_label_the_viewer_or_tell_the_world_story() -> None:
    """產出不說「你是什麼人」：沒有命盤字樣、沒有「你是」、沒有世界裡的地名、沒有檔名；每句 ≤ 60 字。"""
    variants = [BROWSE_THEN_PLAN, PLAN_THEN_BROWSE, BROWSE_THEN_PLAN + [_row(11, "ws_write", "PLAN.md")]]
    seen: list[str] = []
    for rows in variants:
        for files in ({}, {"給誰.md": "收在這裡 留給你"}, {"a.md": "版本一", "b.md": "版本二"}):
            for r in (0, 3):
                seen += _mirror(rows, files=files, retries=r, title="點數單") + _picked(rows, files=files, retries=r, title="點數單")
    assert seen
    banned = ("你是", "MBTI", "星座", "血型", "命盤", "型", ".md", ".txt", "_") + fz.PLACES + tuple(fz.ZODIACS) + fz.MBTI_TYPES
    for x in set(seen):
        assert len(x) + (0 if fz.step_of(x) else len("（第 500 步）")) <= fz.MAX_CARD_LINE_CHARS
        assert not any(b in x for b in banned), x


def _product_only(files):
    return fz._product_files(files)


def test_polaroid_prints_mirror_head_and_first_habit() -> None:
    from ops.exhibit.twin import polaroid as pl
    ok, why = pl.available()
    if not ok:
        pytest.skip(why)
    base = dict(decision="我要整理一份清單", cast_id="c05", date_str="2026-10-12", receipt_short="a1b2c3d4", originals=[])
    _p, m = pl.compose(**base, fortune_line=fz.MIRROR_HEAD, fortune_sentence=fz.polaroid_sentence("先把要做的事寫下來，才開始動手"))
    assert m["fortune_drawn"] is True and m["fortune_chars"] == len(fz.MIRROR_HEAD)
    assert m["caption_source"] == "fortune_sentence"


def test_twinlink_polaroid_and_publish_use_the_mirror_not_the_chart() -> None:
    src = (TWIN / "twinlink.py").read_text(encoding="utf-8")
    i = src.index("png, meta = polaroidlib.compose(")
    call = src[i:src.index("ref = store.vault.seal_polaroid", i)]
    assert "fortune=None" in call and "MIRROR_HEAD" in call and '"first_line"' not in call
    j = src.index('_fz = twin.get("fortune")')
    assert 'or _fz.get("lines")' in src[j:j + 400]                                     # 沒有命盤、有習慣句也送


# ---------------------------------------------------------------------------
# 整合（2026-10-12）：divine 的過程 ＋ mirror 的產出
# ---------------------------------------------------------------------------

def test_integrated_system_files_are_not_things_made() -> None:
    """divine 的 `試的紀錄.md`、PLAN、信不是「做出來的東西」：不當標題、不算成品寫入（不觸發「交出去前又看一遍」）。"""
    rows = BROWSE_THEN_PLAN[:-2] + [_row(9, "ws_write", "成品.md"), _row(10, "ws_write", fz.RECORD_FILE), _row(11, "ws_list", ".")]
    assert any("回頭" in x for x in _mirror(rows))         # 成品之後還有列房間 ⇒ 看了一遍
    only_record_after = BROWSE_THEN_PLAN[:-1] + [_row(10, "ws_write", fz.RECORD_FILE)]
    assert not any("回頭" in x for x in _mirror(only_record_after)), "寫試的紀錄不算看了一遍"
    # 只寫了試的紀錄、沒有任何成品 ⇒ 不當成品（沒有「沒寫計畫就動手」之類的誤判）
    no_art = STAGE1 + [_row(3, "ws_read", "信.md"), _row(4, "ws_read", "地上/草稿角/a.txt"), _row(5, "ws_write", fz.RECORD_FILE)]
    assert _mirror(no_art) == []
    assert fz._product_files({fz.RECORD_FILE: "x", "PLAN.md": "y", "信.md": "z", "鬆環對照冊.md": "w"}) == {"鬆環對照冊.md": "w"}


def test_integrated_changed_mind_counts_within_one_attempt_only() -> None:
    """被閘門退回後重寫計畫是閘門逼的：兩次嘗試各寫一次 PLAN ≠ 改主意（divine 30 張真跑量到不分嘗試會誤判 7 張）。"""
    a1 = BROWSE_THEN_PLAN
    a2 = [_row(1, "ws_read", "信.md"), _row(2, "ws_write", "PLAN.md"), _row(3, "ws_write", "成品.md")]
    for i, r in enumerate(a2):                              # 第二次嘗試：seq 回到 1，時間在後
        r["ts_ms"] = 5000 + i
    two_attempts = a1 + a2
    assert "做到一半改了主意，把計畫重寫了一遍" not in _mirror(two_attempts, retries=1)
    assert "被退回 1 次，每一次都回去改" in _mirror(two_attempts, retries=1)
    same_attempt = a1 + [_row(11, "ws_write", "PLAN.md")]
    assert "做到一半改了主意，把計畫重寫了一遍" in _mirror(same_attempt)


def test_integrated_build_card_keeps_divine_record_but_gives_viewers_only_the_mirror(tmp_path) -> None:
    files = {"PLAN.md": PLAN_TXT, fz.RECORD_FILE: RECORD_TXT, "鬆環對照冊.md": "# 鬆環對照冊\n內文"}
    res, rd, ws = _card(tmp_path, BROWSE_THEN_PLAN, files=files)
    # 給觀眾的
    assert res["head"] == fz.MIRROR_HEAD and 1 <= len(res["lines"]) <= 3
    assert fz.title_of(_product_only(files), fz.resolve(FULL, {})) == "鬆環對照冊", "標題取成品，不是試的紀錄／PLAN"
    assert all(fz.step_of(x) for x in res["lines"]) and [fz.strip_step(x) for x in res["lines"]] == res["tv_lines"]
    banned = (fz.VERDICT_PREFIX, fz.WANT_PREFIX, fz.TRIED_PREFIX, fz.SAID_PREFIX, "其實是", "心裡想", "我想：")
    assert not any(b in x for x in res["lines"] + res["tv_lines"] for b in banned)
    # 過程／紀錄（divine）還在
    assert res["want_line"] and res["tried_line"] and res["said_line"] and res["verdict"]
    saved = json.loads((rd / fz.CARD_JSON_NAME).read_text(encoding="utf-8"))
    assert saved["want_line"] == res["want_line"] and saved["lines_v3"][0] == res["verdict"]
    # 上限：電視 ≤3 句、雲端 ≤4 行、每句 ≤60 字（三處同值）
    assert len(res["tv_lines"]) <= tv.FORTUNE_MAX_LINES == sc.FORTUNE_MAX_LINES == 3
    assert all(0 < len(x) <= tv.FORTUNE_LINE_MAX == sc.FORTUNE_LINE_MAX == fz.MAX_CARD_LINE_CHARS == 60 for x in res["tv_lines"])
    assert fz.MAX_MIRROR_LINES <= 3
    row = {"schema": "twin.sidecar/1", "type": "twin_fortune", "ts_ms": 1, "cell_id": "tw-abc", "run_id": "r", "phase": "card",
           "attempt": 1, "mbti": "INFP", "mbti_source": "ai", "zodiac": "雙魚", "element": "水", "blood": "O",
           "lines": res["tv_lines"]}
    assert sc._fortune_problems(row, 0) == [] and tv.fortune_event_problems({**row, "type": "twin_fortune"}, 0) == []
    # 超過上限的卡會被契約擋下（釘住上限）
    assert sc._fortune_problems({**row, "lines": ["一句"] * 4}, 0) and sc._fortune_problems({**row, "lines": ["長" * 61]}, 0)
    assert len(fz.twin_view(fz.resolve(FULL, {}), res)["lines"]) <= 4
