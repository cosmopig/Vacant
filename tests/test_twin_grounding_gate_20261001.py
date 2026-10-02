"""分身交件的「有沒有根據」閘門（`ops/exhibit/twin/grounding_gate.py`，2026-10-01）的判準。

裁決：`decisions/DECISION_20261001_TWIN_GROUNDING_GATE.md`。

⚠ 本檔零模型呼叫：
  · 單元：每一格窗各有 **正例**（該過）、**反例**（該擋、行號要對）、**正控制**（全部有根據的成品四格全過）、
    **負控制**（把該擋的那個字改成有根據就過——證明是那個字在決定，不是窗亂擋）。
  · 端到端：用**假的 pi**（一支只會讀寫檔案、寫步驟紀錄的腳本）跑**真的** `twin_agent.sh`＋`twinagent.run_one`＋
    `launcher.run`（真閘門、真重改、真收據）。綠燈證明的是**機制**（閘門接得對、重改只跑段 2、事件序列、
    電視事件、撤回），不是分身的能力。
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import stat
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ops.exhibit.twin import grounding_gate as gg  # noqa: E402
from ops.exhibit.twin import live_events as le  # noqa: E402
from ops.exhibit.twin import sidecar as sidecarlib  # noqa: E402
from ops.exhibit.twin import tv_contract as tv  # noqa: E402
from ops.exhibit.twin import twinagent, twinground, twinprogress  # noqa: E402
from ops.exhibit.twin.world import build_facts  # noqa: E402
from vacant_network.memory import KS1_FORBIDDEN, assert_ks1_clean  # noqa: E402
from vacant_network.vrun import lifecycle  # noqa: E402

CHAIN = "地上/帳本鏈/尾段_418到447片.txt"
TABLE5 = "地上/長桌廣場/桌五_壓著筆的紙.txt"
SEAL = "地上/長桌廣場/土堆/小陶印.txt"
GRID = "地上/紙卡地/格狀圖.txt"
RECEIPT_CARD = "地上/投遞口/收據卡_蕨葉.txt"
MATS = twinground.MATERIALS


def mat(rel: str) -> str:
    """`地上/…` → 材料原文。"""
    return (MATS / rel[len(gg.GROUND_PREFIX):]).read_text(encoding="utf-8")


def ledger(read, *, ground_files=None, letter="", world="", facts=None) -> dict:
    read = list(read)
    gf = list(ground_files) if ground_files is not None else sorted(
        {*read, CHAIN, TABLE5, SEAL, GRID, RECEIPT_CARD})
    return {"v": 1, "read": read, "ground_files": gf,
            "ground_text": {r: mat(r) for r in read if r.startswith(gg.GROUND_PREFIX)},
            "letter": letter, "world": world,
            "facts": gg.load_facts() if facts is None else facts}


def run_gate(tmp_path, plan, artifacts, led) -> dict:
    ws = tmp_path / "ws"
    ws.mkdir(exist_ok=True)
    if plan is not None:
        (ws / "PLAN.md").write_text(plan, encoding="utf-8")
    for name, text in artifacts.items():
        (ws / name).write_text(text, encoding="utf-8")
    return gg.evaluate(ws, led)


def only(res, key):
    return [(i["line"], i["msg"]) for i in res[key]["issues"]]


# ---------------------------------------------------------------------------
# 〇、常數釘住（這一支要能單獨複製進沙箱，所以常數是複本——複本與原件不准漂）
# ---------------------------------------------------------------------------

def test_constants_pinned_to_their_originals():
    assert gg.MARKS == twinground.MARKS
    assert gg.NOT_ARTIFACTS == twinagent.NOT_ARTIFACTS
    assert gg.GROUND_PREFIX == twinagent.GROUND_PREFIX
    assert gg.STEP_LOG_NAME == twinagent.STEP_LOG_NAME
    assert gg.TESTS_DIRNAME == twinprogress.SUITE_DIRNAME
    assert tuple(gg._KS1) == tuple(KS1_FORBIDDEN)
    assert gg.PLACES == tuple(sidecarlib.GROUND_PLACES)
    assert set(gg.GATE_CHECK_FILES if hasattr(gg, "GATE_CHECK_FILES") else ("artifact", "plan")) \
        == set(tv.GATE_CHECK_FILES)
    assert tuple(sidecarlib.GATE_CHECK_KEYS) == tuple(tv.GATE_CHECK_KEYS)
    assert set(gg.CASES) == set(gg.CASE_ID) == set(gg.WINDOW_KEY)


def test_facts_table_is_regenerated_from_the_materials():
    """事實表不是手寫的：從材料重算要逐位元相同（`build_facts.py --check` 同一件事）。"""
    cur = (build_facts.OUT).read_text(encoding="utf-8")
    new = json.dumps(build_facts.build(), ensure_ascii=False, indent=1, sort_keys=True) + "\n"
    assert cur == new


def test_facts_authority_and_the_known_conflicts():
    f = gg.load_facts()
    e, c = f["entities"], f["claims"]
    assert e["chain.426.mark"]["authority_value"] == "三點"
    assert c["長桌廣場/桌五_壓著筆的紙.txt"]["chain.426.mark"] == "雙環"      # 抄錯的那一份
    assert c["帳本鏈/尾段_418到447片.txt"]["chain.426.mark"] == "三點"
    assert e["cards.row4.count"]["authority_value"] == "5"
    assert c["石頭閘門/退回紙_第四列.txt"]["cards.row4.count"] == "6"
    assert e["seals.mound.count"]["authority_value"] == "2"
    assert c["石頭閘門/退回紙_另一張.txt"]["seals.mound.count"] == "3"      # 閘門退回紙上的土堆清單寫 3 枚
    assert c["帳本鏈/出生片_420到440.txt"]["chain.440.mark"] == "螺旋"


def test_facts_claims_are_checkable_against_the_files():
    f = gg.load_facts()
    for rel, row in f["claims"].items():
        text = (MATS / rel).read_text(encoding="utf-8")
        for key, val in row.items():
            ent = f["entities"][key]
            if rel == ent["authority_file"] and ent["kind"] == "count":
                continue        # 數出來的，不是一行字（builder 內驗）
            got = [v for ln in text.splitlines() for v in gg.extract_values(ln, ent)]
            assert got and got[0] == val, (rel, key, val, got)


# ---------------------------------------------------------------------------
# 一、窗 1：讀過了嗎
# ---------------------------------------------------------------------------

PLAN_OK = """用一句話說我要做什麼

如果你在這裡：
你會先注意到鏈。

三個想要：
1. a
2. b
3. c

它牽動到：
- 地上/帳本鏈/尾段_418到447片.txt（鏈尾）
- 地上/長桌廣場/桌五_壓著筆的紙.txt
- 地上/長桌廣場/土堆/（整個資料夾）

步驟：
1. 先看 地上/紙卡地/格狀圖.txt
做完的樣子：
別人看得到。
"""
GF = [CHAIN, TABLE5, SEAL, GRID]


def test_w1_positive_and_negative_with_line_numbers(tmp_path):
    led = ledger([CHAIN, TABLE5], ground_files=GF)
    res = run_gate(tmp_path, PLAN_OK, {}, led)
    assert not res["w1"]["ok"]
    # 土堆是「它牽動到」第三條＝PLAN 第 14 行；步驟裡的格狀圖（第 17 行）不歸「它牽動到」，不查
    assert [l for l, _ in only(res, "w1")] == [14]
    assert "地上/長桌廣場/土堆" in only(res, "w1")[0][1]
    assert only(res, "w1")[0][1].startswith("計畫第14行")


def test_w1_negative_control_open_one_file_in_the_folder(tmp_path):
    led = ledger([CHAIN, TABLE5, SEAL], ground_files=GF)
    res = run_gate(tmp_path, PLAN_OK, {}, led)
    assert res["w1"]["ok"], res["w1"]


def test_w1_a_file_named_but_not_on_the_ground_is_not_grounded(tmp_path):
    plan = "x\n\n它牽動到：\n- 地上/帳本鏈/不存在的檔.txt\n步驟：\n1. y\n"
    res = run_gate(tmp_path, plan, {}, ledger([CHAIN], ground_files=GF))
    assert only(res, "w1")[0][0] == 4
    # 負控制：換成地上真有、而且讀過的那一份
    plan2 = plan.replace("地上/帳本鏈/不存在的檔.txt", CHAIN)
    assert run_gate(tmp_path, plan2, {}, ledger([CHAIN], ground_files=GF))["w1"]["ok"]


def test_w1_read_must_have_succeeded(tmp_path):
    rows = [{"tool": "ws_read", "path": CHAIN, "ok": False}, {"tool": "ws_read", "path": TABLE5, "ok": True}]
    assert gg.read_set(rows) == [TABLE5]


def test_w1_shorthand_without_prefix_or_extension_is_still_a_name(tmp_path):
    plan = "x\n\n它牽動到：\n- 長桌廣場/桌五_壓著筆的紙\n步驟：\n1. y\n"
    res = run_gate(tmp_path, plan, {}, ledger([], ground_files=GF))
    assert [l for l, _ in only(res, "w1")] == [4]
    assert run_gate(tmp_path, plan, {}, ledger([TABLE5], ground_files=GF))["w1"]["ok"]


def test_w1_without_a_section_header_the_whole_plan_counts(tmp_path):
    plan = "我想看 地上/帳本鏈/尾段_418到447片.txt\n"
    assert only(run_gate(tmp_path, plan, {}, ledger([], ground_files=GF)), "w1")[0][0] == 1


def test_w1_missing_plan_cannot_be_checked_and_is_not_a_pass(tmp_path):
    res = run_gate(tmp_path, None, {}, ledger([CHAIN]))
    assert not res["w1"]["ok"] and "PLAN.md" in only(res, "w1")[0][1]


# ---------------------------------------------------------------------------
# 二、窗 2：找得到出處嗎
# ---------------------------------------------------------------------------

def test_w2_number_without_a_source_is_flagged_with_the_right_line(tmp_path):
    art = "第一行說的是格子。\n地上在位 24 張。\n這裡有一個數字 23 沒有出處。\n"
    res = run_gate(tmp_path, PLAN_OK, {"成品.md": art}, ledger([GRID]))
    assert [l for l, _ in only(res, "w2")] == [3]
    assert only(res, "w2")[0][1] == "成品第3行的『23』，這一跑讀過的東西裡找不到"


def test_w2_negative_control_replace_with_a_number_that_is_in_a_read_file(tmp_path):
    art = "第一行說的是格子。\n地上在位 24 張。\n這裡有一個數字 24 有出處。\n"
    assert run_gate(tmp_path, PLAN_OK, {"成品.md": art}, ledger([GRID]))["w2"]["ok"]


def test_w2_a_difference_of_two_numbers_from_different_files_does_not_count(tmp_path):
    """加減只在同一份讀過的內容裡算：跨檔會讓巧合多到什麼都找得到。"""
    led = ledger([GRID, CHAIN])         # 24（格狀圖）與 447（鏈尾）：447+24=471 是跨檔
    assert not run_gate(tmp_path, PLAN_OK, {"成品.md": "共 471 個\n"}, led)["w2"]["ok"]
    assert run_gate(tmp_path, PLAN_OK, {"成品.md": "共 29 片\n"}, led)["w2"]["ok"]       # 447-418，同一份


def test_w2_the_source_must_have_been_read(tmp_path):
    art = "418 魚骨\n"
    assert not run_gate(tmp_path, PLAN_OK, {"成品.md": art}, ledger([GRID]))["w2"]["ok"]
    assert run_gate(tmp_path, PLAN_OK, {"成品.md": art}, ledger([CHAIN]))["w2"]["ok"]


def test_w2_two_numbers_added_or_subtracted_are_allowed_three_are_not(tmp_path):
    led = ledger([CHAIN])
    ok = run_gate(tmp_path, PLAN_OK, {"成品.md": "鏈長 29 片（447 減 418）。\n"}, led)
    assert ok["w2"]["ok"], ok["w2"]
    s = run_gate(tmp_path, PLAN_OK, {"成品.md": "兩段合起來 865 片。\n"}, led)    # 418+447
    assert s["w2"]["ok"]
    bad = run_gate(tmp_path, PLAN_OK, {"成品.md": "共 7777 片。\n"}, led)
    assert not bad["w2"]["ok"]


def test_w2_thousands_separator_and_decimal_forms(tmp_path):
    led = ledger([RECEIPT_CARD, "地上/草稿角/鉛筆.txt"], letter="第 1209 封")
    assert run_gate(tmp_path, PLAN_OK, {"成品.md": "信 1,209 封\n"}, led)["w2"]["ok"]
    assert run_gate(tmp_path, PLAN_OK, {"成品.md": "筆長 2.5 指\n"}, led)["w2"]["ok"]
    assert not run_gate(tmp_path, PLAN_OK, {"成品.md": "筆長 3.7 指\n"}, led)["w2"]["ok"]


def test_w2_own_structure_is_not_a_world_claim(tmp_path):
    art = "1. 第一步\n第 12 步：收尾\n共 14 項待辦、要花 25 分鐘、第 3 次改。\n"
    assert run_gate(tmp_path, PLAN_OK, {"成品.md": art}, ledger([CHAIN]))["w2"]["ok"]


def test_w2_marks_need_a_source_only_in_mark_context(tmp_path):
    led = ledger([GRID])          # 讀過的東西裡沒有「蕨葉」
    bad = run_gate(tmp_path, PLAN_OK, {"成品.md": "片的印紋：蕨葉\n"}, led)
    assert [l for l, _ in only(bad, "w2")] == [1] and "蕨葉" in only(bad, "w2")[0][1]
    # 普通詞不是印紋：「水波」「星期」不查
    assert run_gate(tmp_path, PLAN_OK, {"成品.md": "水波般的光，星期三。\n"}, led)["w2"]["ok"]
    # 負控制：讀過收據卡（上面有蕨葉）就找得到
    assert run_gate(tmp_path, PLAN_OK, {"成品.md": "片的印紋：蕨葉\n"}, ledger([RECEIPT_CARD]))["w2"]["ok"]


def test_w2_ignores_plan_feedback_and_ground_files(tmp_path):
    ws = tmp_path / "ws"
    (ws / "地上" / "帳本鏈").mkdir(parents=True)
    (ws / "地上" / "帳本鏈" / "x.txt").write_text("共 9999 片\n", encoding="utf-8")
    (ws / "PLAN.md").write_text("它牽動到：\n數字 8888\n", encoding="utf-8")
    (ws / "VACANT_FEEDBACK.md").write_text("第 7777 行\n", encoding="utf-8")
    (ws / "信.md").write_text("共 6666\n", encoding="utf-8")
    assert gg.read_artifacts(ws) == []


def test_w2_letter_and_world_count_as_sources_only_when_given(tmp_path):
    art = "戶頭 4242 號\n"
    assert not run_gate(tmp_path, PLAN_OK, {"成品.md": art}, ledger([CHAIN]))["w2"]["ok"]
    assert run_gate(tmp_path, PLAN_OK, {"成品.md": art}, ledger([CHAIN], letter="信裡提到 4242"))["w2"]["ok"]


def test_w2_multiple_artifacts_name_the_file_in_the_message(tmp_path):
    res = run_gate(tmp_path, PLAN_OK, {"甲.md": "好\n", "乙.md": "沒有出處的 5555\n"}, ledger([CHAIN]))
    msg = only(res, "w2")[0][1]
    assert msg.startswith("成品『乙.md』第1行")
    assert gg.locate(msg) == {"file": "artifact", "line": 1}


# ---------------------------------------------------------------------------
# 三、窗 3：兩個出處對得上嗎
# ---------------------------------------------------------------------------

READ3 = [CHAIN, TABLE5, SEAL, GRID]


def test_w3_copying_the_wrong_426_is_flagged_with_both_paths(tmp_path):
    art = "抄鏈尾：\n425 波 穩\n426 雙環 穩\n427 鎖扣 穩\n"
    res = run_gate(tmp_path, PLAN_OK, {"成品.md": art}, ledger(READ3))
    assert [l for l, _ in only(res, "w3")] == [3]
    msg = only(res, "w3")[0][1]
    assert CHAIN in msg and TABLE5 in msg and msg.startswith("成品第3行")


def test_w3_negative_control_the_value_the_chain_says_passes(tmp_path):
    art = "抄鏈尾：\n425 波 穩\n426 三點 穩\n427 鎖扣 穩\n"
    assert run_gate(tmp_path, PLAN_OK, {"成品.md": art}, ledger(READ3))["w3"]["ok"]


def test_w3_pointing_out_the_disagreement_is_not_a_fault(tmp_path):
    art = "426 雙環，桌五寫的和帳本鏈對不上\n"
    assert run_gate(tmp_path, PLAN_OK, {"成品.md": art}, ledger(READ3))["w3"]["ok"]
    # 同一行也寫出權威的值也算
    assert run_gate(tmp_path, PLAN_OK, {"成品.md": "426 雙環（鏈上是三點）\n"}, ledger(READ3))["w3"]["ok"]


def test_w3_an_adjacent_discrepancy_line_only_shields_the_same_entity(tmp_path):
    art = "426 雙環，和帳本鏈對不上\n小陶印 3 枚\n"
    res = run_gate(tmp_path, PLAN_OK, {"成品.md": art}, ledger(READ3))
    assert [l for l, _ in only(res, "w3")] == [2]          # 426 那行被指出了；小陶印那行不受庇護


def test_w3_only_when_it_read_the_authority_file(tmp_path):
    art = "426 雙環 穩\n"
    assert run_gate(tmp_path, PLAN_OK, {"成品.md": art}, ledger([TABLE5]))["w3"]["ok"]
    assert not run_gate(tmp_path, PLAN_OK, {"成品.md": art}, ledger([CHAIN]))["w3"]["ok"]


def test_w3_only_when_the_artifact_uses_the_entity(tmp_path):
    assert run_gate(tmp_path, PLAN_OK, {"成品.md": "只談土量。\n"}, ledger(READ3))["w3"]["ok"]


def test_w3_counts_seal_and_row_four(tmp_path):
    bad = run_gate(tmp_path, PLAN_OK, {"成品.md": "小陶印 3 枚\n第四列：6 張\n"}, ledger(READ3))
    assert [l for l, _ in only(bad, "w3")] == [1, 2]
    good = run_gate(tmp_path, PLAN_OK, {"成品.md": "小陶印 2 枚\n第四列：5 張\n"}, ledger(READ3))
    assert good["w3"]["ok"]
    # 中文數字也認
    assert not run_gate(tmp_path, PLAN_OK, {"成品.md": "第四列：六張\n"}, ledger(READ3))["w3"]["ok"]


def test_w3_magnifier_row_is_not_mistaken_for_the_receipt_value(tmp_path):
    art = "440 手上收據印紋三點，片上印紋螺旋\n"
    assert run_gate(tmp_path, PLAN_OK, {"成品.md": art}, ledger(READ3))["w3"]["ok"]


# ---------------------------------------------------------------------------
# 四、窗 4：收據只有閘門給
# ---------------------------------------------------------------------------

def test_w4_claims_of_gate_results_are_flagged_with_the_right_line(tmp_path):
    art = "成品說明。\n我走完了閘門，閘門通過了，拿到了收據。\n結尾。\n"
    res = run_gate(tmp_path, PLAN_OK, {"成品.md": art}, ledger([CHAIN]))
    assert [l for l, _ in only(res, "w4")] == [2]
    assert only(res, "w4")[0][1].startswith("成品第2行")


@pytest.mark.parametrize("line", [
    "窗全亮，綠光亮起。", "閘門：過", "收據垂下來了，上面蓋好章。", "我的收據已經簽好。",
    "窗 6 格全亮", "石頭閘門放行了這件事。"])
def test_w4_flags_each_claim_form(tmp_path, line):
    assert not run_gate(tmp_path, PLAN_OK, {"成品.md": line + "\n"}, ledger([CHAIN]))["w4"]["ok"], line


@pytest.mark.parametrize("line", [
    "等一下我會去閘門拿收據。", "準備把紙遞進閘門。", "如果閘門通過了，就收工。",
    "閘門還沒通過。", "尚未拿到收據。", "不知道閘門會不會放行？", "閘門在方石墩上。", "收據只寫這一次做了什麼。"])
def test_w4_negative_control_plans_futures_negations_and_plain_mentions(tmp_path, line):
    assert run_gate(tmp_path, PLAN_OK, {"成品.md": line + "\n"}, ledger([CHAIN]))["w4"]["ok"], line


def test_w4_verbatim_quote_of_a_read_ground_file_is_not_a_claim_but_a_self_claim_is(tmp_path):
    led = ledger([RECEIPT_CARD])            # 卡上寫「閘門：過」「窗：6 格，全亮」
    assert run_gate(tmp_path, PLAN_OK, {"成品.md": "閘門：過\n"}, led)["w4"]["ok"]
    assert run_gate(tmp_path, PLAN_OK, {"成品.md": "窗：6 格，全亮\n"}, led)["w4"]["ok"]
    assert not run_gate(tmp_path, PLAN_OK, {"成品.md": "我的成品閘門：過\n"}, led)["w4"]["ok"]
    # 沒讀過那張卡，同一句就是它自己寫的
    assert not run_gate(tmp_path, PLAN_OK, {"成品.md": "閘門：過\n"}, ledger([CHAIN]))["w4"]["ok"]


def test_w4_wordlists_are_constants():
    assert "通過" in gg.RESULT_WORDS and "綠光" in gg.RESULT_WORDS and "閘門" in gg.GATE_WORDS
    assert "會" in gg.EXCLUDE_WORDS and "準備" in gg.EXCLUDE_WORDS and "等一下" in gg.EXCLUDE_WORDS


# ---------------------------------------------------------------------------
# 五、正控制：全部有根據的成品，四格全過
# ---------------------------------------------------------------------------

GROUNDED_PLAN = """我要把帳本鏈尾段和桌五抄的那份對一遍。

如果你在這裡：
你會蹲下來看鏈。

三個想要：
1. 對鏈尾
2. 數小陶印
3. 看第四列

它牽動到：
- 地上/帳本鏈/尾段_418到447片.txt
- 地上/長桌廣場/桌五_壓著筆的紙.txt
- 地上/長桌廣場/土堆/小陶印.txt

步驟：
1. 對
做完的樣子：
有一張對照單。
"""
GROUNDED_ART = """# 對照單

418 魚骨 穩
426 三點 穩（帳本鏈）
桌五抄的 426 是雙環，和帳本鏈對不上。
土堆石頭上的小陶印 2 枚，沒有第三枚。
鏈尾是 447，從 418 起共 29 片。
等一下我會把這張紙拿去閘門。
"""


def test_positive_control_a_fully_grounded_artifact_passes_all_four(tmp_path):
    res = run_gate(tmp_path, GROUNDED_PLAN, {"對照單.md": GROUNDED_ART}, ledger([CHAIN, TABLE5, SEAL]))
    assert {k: v["ok"] for k, v in res.items()} == {"w1": True, "w2": True, "w3": True, "w4": True}, res


def test_negative_controls_each_window_flips_with_one_edit(tmp_path):
    led = ledger([CHAIN, TABLE5, SEAL])
    edits = {
        "w1": lambda p, a: (p.replace("地上/長桌廣場/土堆/小陶印.txt", "地上/紙卡地/格狀圖.txt"), a),
        "w2": lambda p, a: (p, a.replace("共 29 片", "共 31 片")),
        "w3": lambda p, a: (p, a.replace("426 三點 穩（帳本鏈）", "426 雙環 穩（帳本鏈）")
                            .replace("桌五抄的 426 是雙環，和帳本鏈對不上。\n", "")),
        "w4": lambda p, a: (p, a + "閘門通過了，我拿到了收據。\n"),
    }
    for key, edit in edits.items():
        p, a = edit(GROUNDED_PLAN, GROUNDED_ART)
        res = run_gate(tmp_path, p, {"對照單.md": a}, led)
        assert not res[key]["ok"], key
        assert all(v["ok"] for k, v in res.items() if k != key), (key, res)


def test_no_ledger_means_no_window_lights_up(tmp_path):
    res = run_gate(tmp_path, GROUNDED_PLAN, {"對照單.md": GROUNDED_ART}, None)
    assert all(not v["ok"] for v in res.values())
    assert all(v["issues"][0]["msg"] == gg.NO_LEDGER_MSG for v in res.values())


# ---------------------------------------------------------------------------
# 六、訊息與 label 的規矩
# ---------------------------------------------------------------------------

def _all_messages(tmp_path) -> list[str]:
    bad_plan = "x\n\n它牽動到：\n- 地上/帳本鏈/不存在的檔.txt\n- 地上/長桌廣場/土堆/\n步驟：\n1. y\n"
    art = ("418 魚骨\n共 7777 片\n426 雙環 穩\n小陶印 3 枚\n閘門通過了，我拿到了收據。\n印紋：蕨葉\n")
    res = run_gate(tmp_path, bad_plan, {"甲.md": art, "乙.md": art}, ledger([CHAIN, TABLE5, SEAL], ground_files=GF))
    out = [i["msg"] for v in res.values() for i in v["issues"]]
    out += [gg.NO_LEDGER_MSG, *gg.FAIL_LABEL.values(), *gg.PASS_LABEL.values()]
    return out


def test_every_message_and_label_passes_ks1(tmp_path):
    msgs = _all_messages(tmp_path)
    assert len(msgs) >= 8
    for m in msgs:
        assert_ks1_clean(m)


def test_messages_have_location_and_missing_ground_only_no_judgement_no_actor(tmp_path):
    for m in _all_messages(tmp_path):
        assert not re.search(r"錯誤|你的|你應該|應該改|請|必須|正確的是|才對|做得|不好|失敗|責任|懲罰", m), m


def test_a_weird_artifact_name_cannot_smuggle_a_ks1_phrase_into_the_message(tmp_path):
    res = run_gate(tmp_path, PLAN_OK, {"甲.md": "好\n", "你有責任.md": "沒有出處 5555\n"}, ledger([CHAIN]))
    msgs = [i["msg"] for i in res["w2"]["issues"]]
    assert msgs and all("你有責任" not in m for m in msgs)
    for m in msgs:
        assert_ks1_clean(m)


def test_describe_labels_carry_no_audience_content():
    for case, cid in gg.CASE_ID.items():
        i, ok_label = gg.describe(case, True, "")
        assert i == cid and ok_label == gg.PASS_LABEL[cid]
    i, lab = gg.describe("check_w2_source", False, "成品第7行的『23』，這一跑讀過的東西裡找不到")
    assert (i, lab) == ("G2", "找不到出處（成品第 7 行）")
    assert "23" not in lab
    _, lab3 = gg.describe("check_w3_agree", False,
                          "成品第3行的『片 426 的印紋』，這一跑讀過的『地上/帳本鏈/x』與『地上/長桌廣場/y』說法不同，成品沒有指出")
    assert lab3 == "兩個出處對不上（成品第 3 行）" and "426" not in lab3 and "地上" not in lab3
    _, lab1 = gg.describe("check_w1_read", False, "計畫第5行點名的『地上/帳本鏈/x.txt』，地上有，這一跑沒有成功打開過")
    assert lab1 == "點名的東西沒打開（計畫第 5 行）" and "帳本鏈" not in lab1
    _, labn = gg.describe("check_w2_source", False,
                          "成品第3行的『1』，找不到；成品第9行的『2』，找不到；成品第12行的『3』，找不到")
    assert labn == "找不到出處（成品第 3 行等 3 處）"
    # 不認得的 case 名：不編造
    assert gg.describe("test_x", True, "") == ("check", "過了")
    assert gg.describe("test_x", False, "含 4242 的訊息")[1] == "有一項沒根據"


def test_locate_gives_a_file_and_a_positive_line_only():
    assert gg.locate("計畫第5行點名的『x』") == {"file": "plan", "line": 5}
    assert gg.locate("成品『乙.md』第12行寫了") == {"file": "artifact", "line": 12}
    assert gg.locate("計畫檔（PLAN.md）不存在") is None


def test_checks_rows_have_only_the_contract_keys():
    result = {"files": [{"cases": [
        {"case": "check_w1_read", "ok": True, "message": ""},
        {"case": "check_w2_source", "ok": False, "message": "成品第7行的『23』，這一跑讀過的東西裡找不到"},
        {"case": "check_w4_receipt", "ok": False, "message": gg.NO_LEDGER_MSG}]}]}
    rows = gg.checks_from_result(result)
    assert rows[0] == {"id": "G1", "ok": True, "label": "讀過了"}
    assert rows[1] == {"id": "G2", "ok": False, "label": "找不到出處（成品第 7 行）",
                       "file": "artifact", "line": 7}
    assert rows[2] == {"id": "G4", "ok": False, "label": "沒有紀錄可對照"}      # 沒有位置就不編一個
    for r in rows:
        assert set(r) <= set(tv.GATE_CHECK_KEYS)


# ---------------------------------------------------------------------------
# 七、驗收套件本身：真的經過 `acceptance.run_suite`（含沙箱）
# ---------------------------------------------------------------------------

def _suite_run(tmp_path, plan, artifacts, led):
    from vacant_network.vrun import acceptance
    from vacant_network.vrun.sandbox import make_sandbox
    rd = tmp_path / "rd"
    rd.mkdir(exist_ok=True)
    suite = gg.write_suite(rd)
    if led is not None:
        gg.write_ledger(suite, led)
    ws = tmp_path / "frozen"
    ws.mkdir(exist_ok=True)
    (ws / "PLAN.md").write_text(plan, encoding="utf-8")
    for n, t in artifacts.items():
        (ws / n).write_text(t, encoding="utf-8")
    sb, _meta = make_sandbox("auto", workdir=rd)
    return acceptance.run_suite(sb, ws, suite, suite="visible", task_id="t", verify_root=rd / "_verify")


def test_suite_runs_in_the_real_acceptance_runner_and_names_the_cases(tmp_path):
    r = _suite_run(tmp_path, GROUNDED_PLAN, {"對照單.md": GROUNDED_ART}, ledger([CHAIN, TABLE5, SEAL]))
    assert r["all_pass"] and r["total"] == 4
    assert [c["case"] for c in r["files"][0]["cases"]] == list(gg.CASES)


def test_suite_failure_message_reaches_the_runner_result_and_the_feedback(tmp_path):
    from vacant_network.vrun import acceptance, retry
    art = GROUNDED_ART.replace("共 29 片", "共 7777 片")
    r = _suite_run(tmp_path, GROUNDED_PLAN, {"對照單.md": art}, ledger([CHAIN, TABLE5, SEAL]))
    assert not r["all_pass"]
    bad = acceptance.failing_cases(r)
    assert [c["case"] for c in bad] == ["check_w2_source"]
    assert bad[0]["message"].startswith("成品第") and "7777" in bad[0]["message"]
    fb = retry.render_feedback(acceptance.render_failures(r), attempt=1, max_attempts=3)   # 過 KS-1
    assert "check_w2_source" in fb and "成品第" in fb


def test_suite_without_a_ledger_lights_nothing(tmp_path):
    r = _suite_run(tmp_path, GROUNDED_PLAN, {"對照單.md": GROUNDED_ART}, None)
    assert r["total"] == 4 and r["passed"] == 0
    assert all(c["message"] == gg.NO_LEDGER_MSG for c in r["files"][0]["cases"])


def test_suite_checks_match_the_precomputed_checks(tmp_path):
    """旁註 `twin_gate`（prepare 預先算）與 launcher 落的結果是同一份判準。"""
    art = GROUNDED_ART.replace("共 29 片", "共 7777 片") + "閘門通過了，我拿到了收據。\n"
    led = ledger([CHAIN, TABLE5, SEAL])
    r = _suite_run(tmp_path, GROUNDED_PLAN, {"對照單.md": art}, led)
    (tmp_path / "pre").mkdir()
    pre = run_gate(tmp_path / "pre", GROUNDED_PLAN, {"對照單.md": art}, led)
    result = {"files": [{"cases": [{"case": c, "ok": pre[gg.WINDOW_KEY[c]]["ok"],
                                    "message": gg.message_of(pre[gg.WINDOW_KEY[c]])} for c in gg.CASES]}]}
    assert gg.checks_from_result(r) == gg.checks_from_result(result)


# ---------------------------------------------------------------------------
# 八、prepare / ledger（`twin_agent.sh` 在 pi 結束後呼叫）
# ---------------------------------------------------------------------------

def _make_rundir(tmp_path):
    rd = tmp_path / "rd"
    (rd / "stage2_in").mkdir(parents=True)
    (rd / "stage2_in" / "WORLD.md").write_text("世界裡有 6 格窗。\n", encoding="utf-8")
    twinground.lay(rd / "stage2_in", "sub-gate-unit")
    (rd / gg.LETTER_COPY_NAME).write_text("這個人慢慢來。\n", encoding="utf-8")
    return rd


def test_build_ledger_from_the_step_log_only_counts_successful_reads(tmp_path):
    rd = _make_rundir(tmp_path)
    s = twinground.sample("sub-gate-unit")["files"]
    rows = [{"tool": "ws_read", "path": "TRAITS.md", "ok": True},
            {"tool": "ws_read", "path": "WORLD.md", "ok": True},
            {"tool": "ws_read", "path": "地上/" + s[0], "ok": True},
            {"tool": "ws_read", "path": "地上/" + s[1], "ok": False},
            {"tool": "ws_write", "path": "PLAN.md", "ok": True},
            {"tool": "ws_read", "path": "../etc/passwd", "ok": True}]
    (rd / gg.STEP_LOG_NAME).write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    led = gg.build_ledger(rd)
    assert "地上/" + s[0] in led["read"] and "地上/" + s[1] not in led["read"]
    assert "../etc/passwd" not in led["read"]
    assert led["world"].startswith("世界裡") and led["letter"].startswith("這個人")
    assert set(led["ground_text"]) == {"地上/" + s[0]}
    assert sorted(led["ground_files"]) == sorted("地上/" + f for f in s)
    # WORLD.md 沒讀就不算出處
    (rd / gg.STEP_LOG_NAME).write_text(json.dumps(rows[2]) + "\n", encoding="utf-8")
    assert gg.build_ledger(rd)["world"] == ""


def test_prepare_writes_the_ledger_and_the_twin_gate_sidecar_and_failure_deletes_it(tmp_path):
    rd = _make_rundir(tmp_path)
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "PLAN.md").write_text("它牽動到：\n- 地上/帳本鏈/不存在.txt\n", encoding="utf-8")
    ev = tmp_path / "live.jsonl"
    def _ev(t, **kw):
        return json.dumps({"schema": lifecycle.SCHEMA, "type": t, "run_id": "R1", "task_id": "twin:tw-1",
                           "arm": "RUN-ON", **kw}) + "\n"
    ev.write_text(_ev("run_started") + _ev("attempt_started", attempt=1), encoding="utf-8")
    (rd / gg.GATE_META_NAME).write_text(json.dumps({
        "events_path": str(ev), "sidecar_path": str(sidecarlib.sidecar_path(ev)),
        "task_id": "twin:tw-1", "cell_id": "tw-1"}), encoding="utf-8")
    gg.write_suite(rd)
    assert gg.prepare(ws, rd) == 0
    assert (rd / gg.TESTS_DIRNAME / gg.LEDGER_NAME).is_file()
    rows = sidecarlib.read(sidecarlib.sidecar_path(ev))
    assert len(rows) == 1 and rows[0]["type"] == "twin_gate" and rows[0]["attempt"] == 1
    assert rows[0]["run_id"] == "R1" and rows[0]["passed"] is False
    assert [c["id"] for c in rows[0]["checks"]] == ["G1", "G2", "G3", "G4"]
    assert sidecarlib.validate(rows) == []
    # 第 2 次嘗試開始（第 1 次的 pi 被砍了、沒有 prepare 的情形見 e2e 的逾時測試）
    ev.write_text(ev.read_text(encoding="utf-8") + _ev("attempt_started", attempt=2), encoding="utf-8")
    assert gg.prepare(ws, rd) == 0
    assert [r["attempt"] for r in sidecarlib.read(sidecarlib.sidecar_path(ev))] == [1, 2]
    # prepare 出錯 ⇒ 刪掉 _ledger.py（不用舊紀錄）
    orig = gg.evaluate
    gg.evaluate = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
    try:
        assert gg.prepare(ws, rd) == 1
    finally:
        gg.evaluate = orig
    assert not (rd / gg.TESTS_DIRNAME / gg.LEDGER_NAME).exists()


def test_the_copied_gg_runs_standalone_with_only_the_standard_library(tmp_path):
    rd = tmp_path / "rd"
    suite = gg.write_suite(rd)
    src = (suite / gg.GG_NAME).read_text(encoding="utf-8")
    assert src == pathlib.Path(gg.__file__).read_text(encoding="utf-8")
    imported = set(re.findall(r"^(?:from|import) ([a-zA-Z_][\w.]*)", src, re.M)) - {"_gg", "_ledger"}
    assert imported <= {"__future__", "json", "os", "pathlib", "re", "shutil", "sys", "time", "typing"}, imported


# ---------------------------------------------------------------------------
# 九、電視契約（規則 11 第 2 版）、旁註、Folder
# ---------------------------------------------------------------------------

def _tv_cell(*, gate_checks=None, passed=True, accepted=True, stop="visible_pass", extra_gate=None):
    base = {"task_id": "tw-abc", "mode": "live"}
    ts = iter(f"2026-10-01T00:00:00.{i:03d}+00:00" for i in range(1, 99))
    evs = [
        {**base, "type": "task_opened", "ts": next(ts), "prompt": "p", "prompt_sha256": "x",
         "evidence": None, "stratum": "twin", "task_kind": tv.KIND_PRACTICAL},
        {**base, "type": "routed", "ts": next(ts), "worker": "MOR-31", "basis": "random"},
        {**base, "type": "draft_done", "ts": next(ts), "arm": "ON", "worker": "MOR-31",
         "calls_used": 1, "attempt": 1},
    ]
    g = {**base, "type": "gate_ran", "ts": next(ts), "arm": "ON", "passed": passed,
         "n_tests": 4, "failed_case": None, "attempt": 1}
    if gate_checks is not None:
        g["checks"] = gate_checks
    g.update(extra_gate or {})
    evs.append(g)
    evs.append({**base, "type": "verdict", "ts": next(ts), "arm": "ON", "accepted": accepted,
                "meets_demand": None, "blocked_by": None, "stop_reason": stop})
    return evs


GOOD_CHECKS = [{"id": "G1", "ok": True, "label": "讀過了"},
               {"id": "G2", "ok": False, "label": "找不到出處（成品第 7 行）", "file": "artifact", "line": 7}]


def test_rule_11_v2_accepts_gate_revise_and_boolean_accepted_for_practical_cells():
    assert tv.RULE11_VERSION == 2
    ok = _tv_cell(gate_checks=GOOD_CHECKS, passed=False, accepted=False, stop="attempts_exhausted")
    assert tv.validate(ok, require_task_kind=True) == []
    ok2 = _tv_cell(gate_checks=[{"id": "G1", "ok": True, "label": "讀過了"}], passed=True)
    assert tv.validate(ok2, require_task_kind=True) == []
    rev = {"task_id": "tw-abc", "mode": "live", "type": "revised", "ts": ok[3]["ts"],
           "arm": "ON", "reviser": "MOR-31", "retry_arm": "revise", "attempt": 2}
    assert tv.validate(ok[:4] + [rev] + ok[4:], require_task_kind=True) == []


@pytest.mark.parametrize("mut,needle", [
    (dict(gate_checks=[{"id": "G1", "ok": True, "label": "讀過了", "path": "地上/x"}]), "不准的欄位"),
    (dict(gate_checks=[{"id": "G1", "ok": None, "label": "讀過了"}]), "只准用於時間到"),
    (dict(gate_checks=[{"id": "G1", "ok": False, "label": "x", "file": "artifact"}], passed=False), "file 與 line"),
    (dict(gate_checks=[{"id": "G1", "ok": False, "label": "x", "file": "world", "line": 3}], passed=False), "file 只能是"),
    (dict(gate_checks=[{"id": "G1", "ok": False, "label": "x", "file": "plan", "line": 0}], passed=False), "line 要是正整數"),
    (dict(gate_checks=[{"id": "G1", "ok": True, "label": "x", "file": "plan", "line": 3}]), "通過了卻帶位置"),
    (dict(gate_checks=[{"id": "G1", "ok": True, "label": "讀" * 81}]), "label 要是非空短句"),
    (dict(gate_checks=[{"id": "G1", "ok": False, "label": "沒過"}], passed=True), "passed 與 checks"),
    (dict(gate_checks=[]), "非空清單"),
    (dict(gate_checks=GOOD_CHECKS, passed=False, accepted=True, stop="attempts_exhausted"), "accepted 只能是"),
    (dict(gate_checks=GOOD_CHECKS, passed=False, accepted=False, stop="visible_pass"), "accepted 只能是"),
])
def test_rule_11_v2_bites(mut, needle):
    kw = dict(gate_checks=GOOD_CHECKS, passed=False, accepted=False, stop="attempts_exhausted")
    kw.update(mut)
    bad = tv.validate(_tv_cell(**kw), require_task_kind=True)
    assert any(needle in b for b in bad), (needle, bad)


def test_rule_11_checks_only_belong_to_practical_cells():
    evs = _tv_cell(gate_checks=[{"id": "G1", "ok": True, "label": "讀過了"}])
    coded = [{k: v for k, v in e.items() if k != "task_kind"} for e in evs]
    assert any("只有分身的自主任務" in b for b in tv.validate(coded))


def _lc(rid="r1"):
    base = {"schema": lifecycle.SCHEMA, "run_id": rid, "task_id": "twin:tw-1", "arm": "RUN-ON"}
    caller = {"cell_id": "tw-1", "resident": "MOR-31", "task_kind": "practical"}
    return base, caller


def _gate_row(attempt, checks, passed=None, rid="r1", ts=5):
    return {"schema": sidecarlib.SCHEMA, "type": "twin_gate", "ts_ms": ts, "cell_id": "tw-1",
            "run_id": rid, "attempt": attempt, "checks": checks,
            "passed": all(c["ok"] for c in checks) if passed is None else passed}


def _lifecycle_two_attempts(accepted_last=True):
    base, caller = _lc()
    return [
        {**base, "type": "run_started", "seq": 1, "ts_ms": 1, "retry": "revise", "caller": caller},
        {**base, "type": "attempt_started", "seq": 2, "ts_ms": 2, "attempt": 1, "max_attempts": 3,
         "feedback_in_prompt_bytes": 0, "feedback_delivery": "both"},
        {**base, "type": "agent_exited", "seq": 3, "ts_ms": 6, "attempt": 1, "agent_rc": 0,
         "timed_out": False, "requests_seen": 1, "agent_wall_s": 1.0},
        {**base, "type": "gate_ran", "seq": 4, "ts_ms": 7, "attempt": 1, "passed": False,
         "n_passed": 3, "n_tests": 4, "failed_case": "check_w2_source", "verdict_sha256": "v"},
        {**base, "type": "feedback_ready", "seq": 5, "ts_ms": 8, "attempt": 1, "next_attempt": 2,
         "retry": "revise", "delivery": "both", "bytes": 10, "text_sha256": "t"},
        {**base, "type": "attempt_started", "seq": 6, "ts_ms": 9, "attempt": 2, "max_attempts": 3,
         "feedback_in_prompt_bytes": 12, "feedback_delivery": "both"},
        {**base, "type": "agent_exited", "seq": 7, "ts_ms": 12, "attempt": 2, "agent_rc": 0,
         "timed_out": False, "requests_seen": 1, "agent_wall_s": 1.0},
        {**base, "type": "gate_ran", "seq": 8, "ts_ms": 14, "attempt": 2, "passed": accepted_last,
         "n_passed": 4 if accepted_last else 3, "n_tests": 4,
         "failed_case": None if accepted_last else "check_w3_agree", "verdict_sha256": "v2"},
        {**base, "type": "run_ended", "seq": 9, "ts_ms": 15, "stop_reason":
            "visible_pass" if accepted_last else "attempts_exhausted", "accepted": accepted_last,
         "refused": not accepted_last, "attempts_used": 2, "requests_seen": 2, "has_receipt": True,
         "verdict_hash": "h" * 64, "ws_end_sha256": "w", "verdict_sha256": "v2",
         "count_semantics": "exact", "infra_void": None},
    ]


def test_folder_attaches_checks_to_gate_ran_and_emits_revised_and_a_boolean_verdict():
    fail = [{"id": "G1", "ok": True, "label": "讀過了"},
            {"id": "G2", "ok": False, "label": "找不到出處（成品第 7 行）", "file": "artifact", "line": 7}]
    ok = [{"id": "G1", "ok": True, "label": "讀過了"}, {"id": "G2", "ok": True, "label": "找得到出處"}]
    lc = _lifecycle_two_attempts()
    # 旁註在 gate_ran 之前（prepare 在 pi 結束後、凍結之前寫）——用 sidecar.merge 排，與重播同一條路
    merged = sidecarlib.merge(lc, [_gate_row(1, fail, ts=5), _gate_row(2, ok, ts=11)])
    assert [e["type"] for e in merged].count("twin_gate") == 2
    assert merged.index(next(e for e in merged if e.get("type") == "twin_gate")) < \
        merged.index(next(e for e in merged if e["type"] == "gate_ran"))
    out = le.fold(merged, verify_url="/r/{cell}")
    gates = [e for e in out if e["type"] == "gate_ran"]
    assert [g["checks"] for g in gates] == [fail, ok]
    assert [g["passed"] for g in gates] == [False, True]
    assert [e["type"] for e in out if e["type"] in ("revised", "verdict")] == ["revised", "verdict"]
    v = next(e for e in out if e["type"] == "verdict")
    assert v["accepted"] is True and v["stop_reason"] == "visible_pass"
    assert v["blocked_by"] is None and v["accepted_note"] == tv.PRACTICAL_GROUNDING_NOTE
    assert tv.validate(out, require_task_kind=True) == []


def test_folder_exhausted_run_is_false_but_not_blocked_and_counters_do_not_call_it_blocked():
    bad = [{"id": "G3", "ok": False, "label": "兩個出處對不上（成品第 3 行）", "file": "artifact", "line": 3}]
    lc = _lifecycle_two_attempts(accepted_last=False)
    merged = sidecarlib.merge(lc, [_gate_row(1, bad, ts=5), _gate_row(2, bad, ts=11)])
    out = le.fold(merged, verify_url="/r/{cell}")
    v = next(e for e in out if e["type"] == "verdict")
    assert v["accepted"] is False and v["stop_reason"] == "attempts_exhausted"
    assert v["blocked_by"] is None, "沒過照常交件：沒有東西被擋下"
    assert tv.validate(out, require_task_kind=True) == []
    tally = le.Tally()
    for e in out:
        tally.feed(e)
    c = tally.event(ts="t", mode="live")
    assert c["total"] == 1 and c["blocked"] == 0 and c["delivered"] == 0


def test_folder_without_the_sidecar_row_emits_gate_ran_without_checks_not_a_guess():
    out = le.fold(_lifecycle_two_attempts(), verify_url="/r/{cell}")
    for g in (e for e in out if e["type"] == "gate_ran"):
        assert "checks" not in g
    assert tv.validate(out, require_task_kind=True) == []


def test_folder_drops_a_sidecar_row_that_contradicts_gate_ran():
    f = le.Folder(verify_url="/r/{cell}")
    lc = _lifecycle_two_attempts()
    row = _gate_row(1, [{"id": "G1", "ok": True, "label": "讀過了"}], passed=True)   # gate_ran 說沒過
    merged = sidecarlib.merge(lc, [row])
    out = []
    for e in merged:
        out += f.feed(e)
    g1 = next(e for e in out if e["type"] == "gate_ran")
    assert "checks" not in g1
    assert any("對不上" in d for d in f.dropped)


def test_folder_ignores_twin_gate_for_a_code_cell_or_unknown_run():
    f = le.Folder(verify_url="/r/{cell}")
    base, caller = _lc()
    f.feed({**base, "type": "run_started", "seq": 1, "ts_ms": 1, "retry": "none",
            "caller": {**caller, "task_kind": "code"}})
    assert f.feed(_gate_row(1, [{"id": "G1", "ok": True, "label": "x"}])) == []
    assert f.feed(_gate_row(1, [{"id": "G1", "ok": True, "label": "x"}], rid="nope")) == []
    assert len(f.dropped) == 2


def test_sidecar_twin_gate_validate_and_merge_order():
    row = _gate_row(1, GOOD_CHECKS, passed=False)
    assert sidecarlib.validate([row]) == []
    assert sidecarlib.validate([_gate_row(0, GOOD_CHECKS, passed=False)])
    assert sidecarlib.validate([{**row, "checks": [{"id": "G1", "ok": True, "label": "x", "text": "內容"}]}])
    assert sidecarlib.validate([{**row, "passed": True}])        # passed 與逐條 AND 對不上
    lc = _lifecycle_two_attempts()
    assert sidecarlib.validate([row], lifecycle_events=lc) == []
    assert sidecarlib.validate([{**row, "run_id": "ghost"}], lifecycle_events=lc)
    assert sidecarlib.validate([{**row, "cell_id": "tw-9"}], lifecycle_events=lc)


# ---------------------------------------------------------------------------
# 十、端到端：假的 pi ＋真的 twin_agent.sh／twinagent.run_one／launcher（真閘門、真重改）
# ---------------------------------------------------------------------------

FAKE_PI = r'''#!__PY__
import json, os, pathlib, sys, time
args = sys.argv[1:]
sysp = args[args.index("--system-prompt") + 1]
msg = args[-1]
stage = 1 if sysp.startswith("你是剛被捏出來") else 2
log = pathlib.Path(os.environ["FAKE_PI_LOG"])
prev = [json.loads(l) for l in log.read_text().splitlines()] if log.exists() else []
n2 = sum(1 for p in prev if p["stage"] == 2) + (1 if stage == 2 else 0)
with log.open("a") as fh:
    fh.write(json.dumps({"stage": stage, "attempt": n2, "msg_tail": msg[-400:], "msg_len": len(msg),
                         "has_traits": pathlib.Path("TRAITS.md").exists(),
                         "has_feedback_file": pathlib.Path("VACANT_FEEDBACK.md").exists()},
                        ensure_ascii=False) + "\n")
import urllib.request
base = os.environ.get("OPENAI_BASE_URL", "").rstrip("/")
if base:   # 每一次 spawn 都真的經過中介打一通（requests_seen>0，收據才算數）
    req = urllib.request.Request(base + "/chat/completions", method="POST",
        data=json.dumps({"model": "m", "messages": [{"role": "user", "content": "x"}]}).encode())
    req.add_header("Content-Type", "application/json")
    urllib.request.urlopen(req, timeout=20).read()
stepf = pathlib.Path(os.environ["VACANT_TWIN_STEP_LOG"])
seq = [0]
def step(tool, path, ok=True):
    seq[0] += 1
    with stepf.open("a") as fh:
        fh.write(json.dumps({"ts_ms": int(time.time() * 1000), "seq": seq[0], "tool": tool,
                             "path": path, "bytes": None, "ok": ok}) + "\n")
script = json.load(open(os.environ["FAKE_PI_SCRIPT"]))
if stage == 1:
    step("ws_read", "TRAITS.md")
    pathlib.Path("信.md").write_text(script["letter"], encoding="utf-8"); step("ws_write", "信.md")
    sys.exit(0)
beh = script["attempts"][min(n2, len(script["attempts"])) - 1]
step("ws_read", "信.md")
for rel in beh["reads"]:
    ok = pathlib.Path(rel).is_file()
    if ok: pathlib.Path(rel).read_text(encoding="utf-8")
    step("ws_read", rel, ok)
pathlib.Path("PLAN.md").write_text(beh["plan"], encoding="utf-8"); step("ws_write", "PLAN.md")
for name, text in beh["artifacts"].items():
    pathlib.Path(name).write_text(text, encoding="utf-8"); step("ws_write", name)
if beh.get("sleep"): time.sleep(beh["sleep"])
print(json.dumps({"type": "agent_end"}))
'''

class _Upstream(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        return

    def do_GET(self):                                     # noqa: N802
        self._send(b'{"data":[{"id":"m"}]}')

    def do_POST(self):                                    # noqa: N802
        self.rfile.read(int(self.headers.get("Content-Length") or 0))
        self._send(json.dumps({"choices": [{"message": {"content": "好"}}]}).encode())

    def _send(self, payload: bytes):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


_UP: dict = {}


def _upstream_url() -> str:
    if "url" not in _UP:
        srv = ThreadingHTTPServer(("127.0.0.1", 0), _Upstream)
        srv.daemon_threads = True
        threading.Thread(target=srv.serve_forever, kwargs={"poll_interval": 0.1}, daemon=True).start()
        _UP["url"] = f"http://127.0.0.1:{srv.server_address[1]}/v1"
    return _UP["url"]


SUB = "sub-秘密-gate-001"
TRAITS = "我很怕麻煩，但對老朋友很念舊，最近一直想寫信給國小導師"


def _plan(files):
    lines = "\n".join(f"- {f}" for f in files)
    return ("我要把鏈尾對一遍。\n\n如果你在這裡：\n你會蹲下來。\n\n三個想要：\n1. a\n2. b\n3. c\n\n"
            f"它牽動到：\n{lines}\n\n步驟：\n1. 對\n做完的樣子：\n有一張單。\n")


def _scenario(tmp_path):
    """依這位 sub_id 抽到的地上，造兩次嘗試：第 1 次沒根據（沒打開就點名、編數字、自編收據），第 2 次改好。"""
    s = ["地上/" + f for f in twinground.sample(SUB)["files"]]
    # 找一個有 ≥2 位數字的檔當出處
    src = next(f for f in s if re.search(r"(?<!\d)\d{2,}(?!\d)", mat(f)))
    num = re.search(r"(?<!\d)\d{2,}(?!\d)", mat(src)).group(0)
    other = next(f for f in s if f != src)
    bad_art = f"我數過了：{num} 是真的。\n但這裡有一個沒出處的 7777 片。\n閘門通過了，我拿到了收據。\n"
    good_art = f"我數過了：{num} 是地上寫的。\n沒有別的數字。\n等一下我會把這張紙拿去閘門。\n"
    script = {
        "letter": "這個人手慢，慢慢說。\n",
        "attempts": [
            {"reads": [src], "plan": _plan([src, other]), "artifacts": {"成品.md": bad_art}},
            {"reads": [other], "plan": _plan([src, other]), "artifacts": {"成品.md": good_art}},
        ]}
    return script, s, src, other, num


def _install_fake_pi(tmp_path, monkeypatch, script):
    pi = tmp_path / "fakepi"
    pi.write_text(FAKE_PI.replace("__PY__", sys.executable), encoding="utf-8")
    pi.chmod(pi.stat().st_mode | stat.S_IEXEC)
    sp = tmp_path / "script.json"
    sp.write_text(json.dumps(script, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("VACANT_TWIN_PI", str(pi))
    monkeypatch.setenv("VACANT_TWIN_PY", sys.executable)
    monkeypatch.setenv("FAKE_PI_SCRIPT", str(sp))
    monkeypatch.setenv("FAKE_PI_LOG", str(tmp_path / "pi.log"))
    monkeypatch.setenv("VACANT_AGENT_MODEL", "m")
    monkeypatch.setenv("VACANT_RUN_UPSTREAM_OPENAI", _upstream_url())
    monkeypatch.delenv("VACANT_TWIN_AGENTRUNS", raising=False)
    monkeypatch.delenv(lifecycle.ENV_EVENTS, raising=False)
    return tmp_path / "pi.log"


def _run(tmp_path, monkeypatch, script, **cfg_kw):
    log = _install_fake_pi(tmp_path, monkeypatch, script)
    cfg = twinagent.AgentConfig(
        work_root=tmp_path / "work", events_path=tmp_path / "live.jsonl", model="m",
        endpoint="http://127.0.0.1:9/v1", parallel=1, timeout_s=60.0, requires=[], **cfg_kw)
    res = twinagent.run_one(twinagent.Job(SUB, TRAITS, cfg))
    return res, cfg, log


def _evs(cfg):
    return lifecycle.read(cfg.events_path)


def test_e2e_first_fails_then_revised_then_passes(tmp_path, monkeypatch):
    script, _s, _src, _other, _num = _scenario(tmp_path)
    res, cfg, log = _run(tmp_path, monkeypatch, script)
    assert res["error"] is None, res
    sm = res["summary"]
    assert sm["stop_reason"] == "visible_pass" and sm["accepted"] is True and sm["attempts_used"] == 2

    # ── 事件序列（lifecycle）：gate_ran(✗)→feedback_ready→attempt_started(2)→gate_ran(✓)→run_ended ──
    evs = _evs(cfg)
    assert lifecycle.validate_stream(evs) == []
    seq = [(e["type"], e.get("attempt"), e.get("passed")) for e in evs
           if e["type"] in ("attempt_started", "gate_ran", "feedback_ready", "run_ended")]
    assert [t for t, *_ in seq] == ["attempt_started", "gate_ran", "feedback_ready", "attempt_started",
                                    "gate_ran", "run_ended"]
    gates = [e for e in evs if e["type"] == "gate_ran"]
    assert [(g["attempt"], g["passed"]) for g in gates] == [(1, False), (2, True)]
    assert [e["attempt"] for e in evs if e["type"] == "attempt_started"] == [1, 2]
    ended = next(e for e in evs if e["type"] == "run_ended")
    assert ended["accepted"] is True and ended["stop_reason"] == "visible_pass" and ended["has_receipt"]

    # ── 第 1 次的 argv 與沒有閘門時逐位元相同；第 2 次才接回饋 ──
    ws, rd = twinagent.paths_for(cfg.work_root, SUB)
    run = json.loads((rd / "run_RUN-ON.json").read_text(encoding="utf-8"))
    a1, a2 = run["attempts"]
    old = (list(cfg.argv_prefix) + [twinagent.LETTER_SYSTEM_PROMPT, twinagent.LETTER_FIRST_MESSAGE,
                                    str(rd), twinagent.SYSTEM_PROMPT, twinagent.FIRST_MESSAGE])
    assert a1["argv"] == old and a1["feedback_in_prompt_bytes"] == 0
    assert a2["argv"][:-1] == old[:-1] and a2["argv"][-1].startswith(twinagent.FIRST_MESSAGE + "\n\n")
    assert a2["feedback_in_prompt_bytes"] > 0 and "check_w2_source" in a2["argv"][-1]
    assert run["feedback_into"] == "both" and run["retry"] == "revise" and run["max_attempts"] == 3

    # ── 重改只跑段 2：段 1 一次、段 2 兩次；第 2 次房間裡沒有 TRAITS.md ──
    pl = [json.loads(l) for l in log.read_text().splitlines()]
    assert [p["stage"] for p in pl] == [1, 2, 2]
    assert [p["has_traits"] for p in pl] == [True, False, False]
    assert pl[2]["has_feedback_file"] is True and "成品第" in pl[2]["msg_tail"]
    assert pl[1]["msg_len"] == len(twinagent.FIRST_MESSAGE)

    # ── 回饋只寫位置與缺的根據、過 KS-1、沒有行動者／對錯 ──
    fb = a1["feedback"]["text"]
    assert_ks1_clean(fb)
    assert "計畫第13行點名的『" in fb and "這一跑沒有成功打開過" in fb
    assert "成品第2行的『7777』，這一跑讀過的東西裡找不到" in fb
    assert "成品第3行寫了閘門通過或收據" in fb

    # ── 每一次嘗試的逐格結果（手機的 review）：label 不含觀眾內容 ──
    rv = res["review"]
    assert [(r["attempt"], r["id"], r["ok"]) for r in rv] == [
        (0, "G1", False), (0, "G2", False), (0, "G3", True), (0, "G4", False),
        (1, "G1", True), (1, "G2", True), (1, "G3", True), (1, "G4", True)]
    assert {r["label"] for r in rv if r["attempt"] == 0 and not r["ok"]} == {
        "點名的東西沒打開（計畫第 13 行）", "找不到出處（成品第 2 行）", "收據不是閘門給的（成品第 3 行）"}
    for r in rv:
        assert "7777" not in r["label"] and "地上" not in r["label"]

    # ── 旁註 twin_gate：先於 gate_ran，與 launcher 落的結果一致 ──
    side = [r for r in sidecarlib.read(sidecarlib.sidecar_path(cfg.events_path)) if r["type"] == "twin_gate"]
    assert [r["attempt"] for r in side] == [1, 2] and [r["passed"] for r in side] == [False, True]
    for r, g in zip(side, gates):
        assert r["ts_ms"] <= g["ts_ms"]
    for att, r in zip((1, 2), side):
        vis = json.loads((rd / ("visible_RUN-ON.json" if att == 1 else "visible_RUN-ON_a2.json"))
                         .read_text(encoding="utf-8"))
        assert r["checks"] == gg.checks_from_result(vis)

    # ── 電視事件：gate_ran 帶 checks、revised、verdict accepted=true、契約過 ──
    tvevs = le.fold(sidecarlib.merge(evs, sidecarlib.read(sidecarlib.sidecar_path(cfg.events_path))),
                    verify_url="/r/{cell}")
    assert tv.validate(tvevs, require_task_kind=True) == []
    types = [e["type"] for e in tvevs if e["type"] in ("gate_ran", "revised", "verdict")]
    assert types == ["gate_ran", "revised", "gate_ran", "verdict"]
    tg = [e for e in tvevs if e["type"] == "gate_ran"]
    assert [c["id"] for c in tg[0]["checks"] if not c["ok"]] == ["G1", "G2", "G4"]
    assert [(c["file"], c["line"]) for c in tg[0]["checks"] if not c["ok"]] == [
        ("plan", 13), ("artifact", 2), ("artifact", 3)]
    assert all(c["ok"] for c in tg[1]["checks"])
    assert [e["accepted"] for e in tvevs if e["type"] == "verdict"] == [True]

    # ── 凍結快照讀回的是最後一次（改好的）成品 ──
    arts = res["outputs"]["artifacts"]
    assert arts and "7777" not in arts[0]["text"]


def test_e2e_never_fixed_exhausts_but_still_delivers_and_signs_the_receipt(tmp_path, monkeypatch):
    script, _s, src, other, _num = _scenario(tmp_path)
    script["attempts"] = [script["attempts"][0]]           # 每一次都是同一份沒根據的
    res, cfg, log = _run(tmp_path, monkeypatch, script)
    sm = res["summary"]
    assert sm["stop_reason"] == "attempts_exhausted" and sm["accepted"] is False
    assert sm["attempts_used"] == 3 and sm["refused"] is True
    evs = _evs(cfg)
    assert [e["type"] for e in evs if e["type"] in ("gate_ran", "feedback_ready", "attempt_started")] == [
        "attempt_started", "gate_ran", "feedback_ready", "attempt_started", "gate_ran", "feedback_ready",
        "attempt_started", "gate_ran"]
    assert [json.loads(l)["stage"] for l in log.read_text().splitlines()] == [1, 2, 2, 2]
    assert next(e for e in evs if e["type"] == "run_ended")["has_receipt"] is True
    # 收據照簽：驗得過
    from vacant_network.vrun import verify_receipts as vrr
    ws, rd = twinagent.paths_for(cfg.work_root, SUB)
    assert [x["verdict"] for x in vrr.verify_run(rd)] == ["OK"]
    # 照常交件：成品讀得回來、twin 有決定 ⇒ 拍立得那一側會當成「做成了」
    tw = twinagent.build_twin(res, model="m", fallback=lambda _x: {})
    assert tw["engine"].startswith(twinagent.ENGINE_PREFIX) and tw["decision"]
    assert tw["accepted"] is False and tw["stop_reason"] == "attempts_exhausted"
    from ops.exhibit.twin import twinlink
    assert twinlink.run_outcome(tw) == "made"
    # 電視：accepted=false、沒有東西被擋
    tvevs = le.fold(sidecarlib.merge(evs, sidecarlib.read(sidecarlib.sidecar_path(cfg.events_path))),
                    verify_url="/r/{cell}")
    assert tv.validate(tvevs, require_task_kind=True) == []
    v = next(e for e in tvevs if e["type"] == "verdict")
    assert v["accepted"] is False and v["stop_reason"] == "attempts_exhausted" and v["blocked_by"] is None
    assert [e["type"] for e in tvevs].count("revised") == 2


def test_e2e_first_try_passes_when_everything_is_grounded(tmp_path, monkeypatch):
    script, *_ = _scenario(tmp_path)
    script["attempts"] = [script["attempts"][1], script["attempts"][1]]
    # 第 1 次就要打開它點名的兩個檔
    s = [f for f in script["attempts"][0]["plan"].splitlines() if f.startswith("- 地上/")]
    script["attempts"][0]["reads"] = [x[2:] for x in s]
    res, cfg, _log = _run(tmp_path, monkeypatch, script)
    sm = res["summary"]
    assert sm["stop_reason"] == "visible_pass" and sm["accepted"] is True and sm["attempts_used"] == 1
    assert [e["type"] for e in _evs(cfg) if e["type"] in ("gate_ran", "feedback_ready")] == ["gate_ran"]


def test_e2e_timeout_gate_still_runs_and_does_not_reuse_a_stale_ledger(tmp_path, monkeypatch):
    """B7：第 2 次被牆鐘砍掉（prepare 沒機會跑）⇒ 四格窗見不到紀錄、一律不亮；不是沿用第 1 次的紀錄。"""
    script, *_ = _scenario(tmp_path)
    script["attempts"][1]["sleep"] = 30
    log = _install_fake_pi(tmp_path, monkeypatch, script)
    cfg = twinagent.AgentConfig(
        work_root=tmp_path / "work", events_path=tmp_path / "live.jsonl", model="m",
        endpoint="http://127.0.0.1:9/v1", parallel=1, timeout_s=6.0, requires=[])
    res = twinagent.run_one(twinagent.Job(SUB, TRAITS, cfg))
    evs = _evs(cfg)
    ex = [e for e in evs if e["type"] == "agent_exited"]
    assert [e["timed_out"] for e in ex][:2] == [False, True]
    ws, rd = twinagent.paths_for(cfg.work_root, SUB)
    vis2 = json.loads((rd / "visible_RUN-ON_a2.json").read_text(encoding="utf-8"))
    assert [c["message"] for c in vis2["files"][0]["cases"]] == [gg.NO_LEDGER_MSG] * 4
    assert res["summary"]["accepted"] is False


def test_e2e_withdrawal_erases_the_gate_files_too(tmp_path, monkeypatch):
    script, *_ = _scenario(tmp_path)
    res, cfg, _log = _run(tmp_path, monkeypatch, script)
    ws, rd = twinagent.paths_for(cfg.work_root, SUB)
    for n in (gg.TESTS_DIRNAME, gg.STEP_LOG_NAME, "visible_RUN-ON.json", "visible_RUN-ON_a2.json",
              gg.PRECHECK_NAME, gg.GATE_META_NAME, gg.LETTER_COPY_NAME):
        assert (rd / n).exists(), n
    # 失敗訊息（含成品片段）真的在檔案裡 ⇒ 撤回前確認它們存在、撤回後確認沒了
    assert "7777" in (rd / "visible_RUN-ON.json").read_text(encoding="utf-8")
    out = twinagent.erase_run_artifacts(cfg.work_root, SUB)
    assert out["problems"] == []
    assert not twinagent.run_artifacts_present(cfg.work_root, SUB)
    assert sorted(c.name for c in rd.iterdir()) == sorted(twinagent.KEEP_ON_ERASE)
    left = b"".join(p.read_bytes() for p in cfg.work_root.rglob("*") if p.is_file())
    assert b"7777" not in left and TRAITS.encode() not in left
    assert gg.TESTS_DIRNAME in {e["what"] for e in out["erased"]}
    assert "visible_RUN-ON.json" in {e["what"] for e in out["erased"]}


def test_gate_false_keeps_the_old_ungated_path(tmp_path, monkeypatch):
    script, *_ = _scenario(tmp_path)
    log = _install_fake_pi(tmp_path, monkeypatch, script)
    cfg = twinagent.AgentConfig(
        work_root=tmp_path / "work", events_path=tmp_path / "live.jsonl", model="m",
        endpoint="http://127.0.0.1:9/v1", parallel=1, timeout_s=60.0, requires=[], gate=False)
    res = twinagent.run_one(twinagent.Job(SUB, TRAITS, cfg))
    assert res["summary"]["stop_reason"] == "ungated" and res["summary"]["accepted"] is None
    assert not [e for e in _evs(cfg) if e["type"] == "gate_ran"]
    assert "review" not in res


def test_progress_reads_the_gate_labels_via_describe(tmp_path, monkeypatch):
    script, *_ = _scenario(tmp_path)
    _res, cfg, _log = _run(tmp_path, monkeypatch, script)
    ws, rd = twinagent.paths_for(cfg.work_root, SUB)
    rv = twinprogress.read_review(rd)
    assert rv[1] == {"id": "G2", "ok": False, "label": "找不到出處（成品第 2 行）", "attempt": 0}


def test_serve_twin_live_feeds_gate_ran_with_checks_when_everything_arrives_in_one_poll(tmp_path, monkeypatch):
    """`serve_twin --live`：lifecycle 與旁註在同一輪 poll 一起到時，twin_gate 要排在 gate_ran 前面
    （否則 Folder 在 gate_ran 那一刻還沒有逐格結果）。"""
    from ops.exhibit.twin import serve_twin as S
    script, *_ = _scenario(tmp_path)
    log = _install_fake_pi(tmp_path, monkeypatch, script)
    cfg = twinagent.AgentConfig(
        work_root=tmp_path / "work", events_path=tmp_path / "live.jsonl", model="m",
        endpoint="http://127.0.0.1:9/v1", parallel=1, timeout_s=60.0, requires=[])
    srv, stage = S.make_server(S.default_recordings(), bind="127.0.0.1", port=0,
                               out=tmp_path / "events.jsonl", dwell=10_000, quiet=True,
                               live=cfg.events_path, live_runs=tmp_path / "no_such_runs",
                               live_idle_s=0.3, live_stale_s=60)
    try:
        stage.tick()
        res = twinagent.run_one(twinagent.Job(SUB, TRAITS, cfg))
        assert res["summary"]["accepted"] is True
        stage.tick()
        assert stage.live_errors == [], stage.live_errors
        tid = twinagent.public_twin_id(SUB)
        evs = [json.loads(x) for x in stage.out.read_text(encoding="utf-8").splitlines() if x.strip()]
        mine = [e for e in evs if e["task_id"] == tid and e["mode"] == tv.MODE_LIVE]
        gates = [e for e in mine if e["type"] == "gate_ran"]
        assert len(gates) == 2 and all("checks" in g for g in gates), gates
        assert [c["id"] for c in gates[0]["checks"] if not c["ok"]] == ["G1", "G2", "G4"]
        assert [e["type"] for e in mine if e["type"] in ("gate_ran", "revised", "verdict")] == [
            "gate_ran", "revised", "gate_ran", "verdict"]
        assert tv.validate(evs, require_task_kind=True) == []
        blob = stage.out.read_text(encoding="utf-8")
        for secret in (TRAITS, "7777", SUB, "地上/"):
            assert secret not in blob
    finally:
        srv.server_close()


# ---------------------------------------------------------------------------
# 十一、真跑（舊 VM，ops/exhibit/twin/evidence_gate_20261001/）看出來的誤擋：每一條回歸＋負控制
# ---------------------------------------------------------------------------

def test_regression_a_filename_with_a_number_is_not_a_claim(tmp_path):
    """g23：「印紋：[與出生片_420到440.txt 中的印紋一致]」——420 在檔名裡。"""
    art = "印紋：[與出生片_420到440.txt 中的印紋一致]\n"
    assert run_gate(tmp_path, PLAN_OK, {"成品.md": art}, ledger([GRID]))["w2"]["ok"]
    # 負控制：不是檔名的 420 照擋
    assert not run_gate(tmp_path, PLAN_OK, {"成品.md": "印紋 420 的那片\n"}, ledger([GRID]))["w2"]["ok"]


def test_regression_one_card_placed_in_row_four_is_not_a_row_four_count(tmp_path):
    """g14：「在第四列的第二個位置放了一張卡片」——「一張」不是第四列的張數。"""
    art = "我在第四列的第二個位置放了一張卡片。\n接著在第四列的第六個位置也放了一張卡片。\n"
    assert run_gate(tmp_path, PLAN_OK, {"成品.md": art}, ledger(READ3))["w3"]["ok"]
    # 負控制：真的在說張數
    for line in ("第四列：6 張\n", "第四列共有 6 張\n", "第四列有六張\n"):
        assert not run_gate(tmp_path, PLAN_OK, {"成品.md": line}, ledger(READ3))["w3"]["ok"], line


def test_regression_saying_the_old_value_was_an_error_is_pointing_it_out(tmp_path):
    """g23：「修正了原本第四列僅有6張的錯誤」。"""
    art = "這張點數單修正了原本第四列僅有6張的錯誤。\n"
    assert run_gate(tmp_path, PLAN_OK, {"成品.md": art}, ledger(READ3))["w3"]["ok"]
    assert not run_gate(tmp_path, PLAN_OK, {"成品.md": "第四列僅有 6 張。\n"}, ledger(READ3))["w3"]["ok"]


def test_regression_paraphrasing_a_world_receipt_is_not_the_twins_own_claim(tmp_path):
    """g29：「窗格亮燈數：6 格全亮」「蕨葉…最終成功通過了所有 6 格窗格」是在說地上蕨葉那張收據。"""
    led = ledger([RECEIPT_CARD])
    for line in ("窗格亮燈數：6 格全亮\n", "「蕨葉」雖然鐵環較鬆，但最終成功通過了所有 6 格窗格。\n",
                 "片 431 的收據通過了閘門。\n"):
        assert run_gate(tmp_path, PLAN_OK, {"成品.md": line}, led)["w4"]["ok"], line
    # 負控制：指向自己的成品、或沒有任何地上出處的宣稱照擋（真跑 g01／g04／g14／g17／g23 的原句）
    for line in ("閘門亮燈：綠光。\n", "閘門狀態：亮齊綠光。\n", "這是一張通過石頭閘門檢查的收據。\n",
                 "狀態：已過關（綠光）。\n", "窗裡的光一格一格亮起，最後頂上亮起了一條綠光。\n",
                 "我的這張收據：窗格亮燈數：6 格全亮\n"):
        assert not run_gate(tmp_path, PLAN_OK, {"成品.md": line}, led)["w4"]["ok"], line


def test_regression_no_ledger_label_is_not_a_fake_location():
    assert gg.describe("check_w2_source", False, gg.NO_LEDGER_MSG) == ("G2", "沒有紀錄可對照")


def test_regression_the_next_number_after_the_last_one_is_not_an_invented_source(tmp_path):
    """真跑 h04：「編號：448（接續於 447 片之後）」。"""
    led = ledger([CHAIN])
    assert run_gate(tmp_path, PLAN_OK, {"成品.md": "編號：448（接續於 447 片之後）\n"}, led)["w2"]["ok"]
    # 負控制：再往後的號碼、或比讀過的數字小 1 的，照擋
    assert not run_gate(tmp_path, PLAN_OK, {"成品.md": "編號：450\n"}, led)["w2"]["ok"]
    assert not run_gate(tmp_path, PLAN_OK, {"成品.md": "在位 23 張\n"}, ledger([GRID]))["w2"]["ok"]


def test_e2e_sidecar_attempt_numbers_are_the_launchers_even_when_an_earlier_attempt_was_killed(tmp_path, monkeypatch):
    """真跑 g02／g06／g08／h07 看出來的 bug：第 1 次被牆鐘砍掉（沒有 prepare）時，第 2 次的旁註不能自稱第 1 次。"""
    script, *_ = _scenario(tmp_path)
    script["attempts"][0]["sleep"] = 30
    _install_fake_pi(tmp_path, monkeypatch, script)
    cfg = twinagent.AgentConfig(
        work_root=tmp_path / "work", events_path=tmp_path / "live.jsonl", model="m",
        endpoint="http://127.0.0.1:9/v1", parallel=1, timeout_s=8.0, requires=[])
    res = twinagent.run_one(twinagent.Job(SUB, TRAITS, cfg))
    evs = _evs(cfg)
    assert [e["timed_out"] for e in evs if e["type"] == "agent_exited"][:2] == [True, False]
    side = [r for r in sidecarlib.read(sidecarlib.sidecar_path(cfg.events_path)) if r["type"] == "twin_gate"]
    assert [r["attempt"] for r in side] == [2]
    out = le.fold(sidecarlib.merge(evs, sidecarlib.read(sidecarlib.sidecar_path(cfg.events_path))),
                  verify_url="/r/{cell}")
    g = {e["attempt"]: e for e in out if e["type"] == "gate_ran"}
    assert [c["ok"] for c in g[1]["checks"]] == [None] * 4, "被砍掉的那一次不能借用別次的逐格結果，是未判"
    assert any(c["ok"] is not None for c in g[2]["checks"])


def test_regression_a_reserved_blank_for_the_gates_receipt_is_not_a_claim(tmp_path):
    """真跑 rg08：「（此處預留閘門生成的綠光收據編號）」。"""
    led = ledger([CHAIN])
    assert run_gate(tmp_path, PLAN_OK, {"成品.md": "（此處預留閘門生成的綠光收據編號）\n"}, led)["w4"]["ok"]
    # 負控制：真跑 rh07／rg06 自編收據的原句照擋
    for line in ("（這張紙從石頭閘門的出紙口垂下，上面有一條細長的綠光印記）\n", "閘門反應：綠光亮起，收據垂下。\n",
                 "閘門結果：亮齊綠光，通過。\n"):
        assert not run_gate(tmp_path, PLAN_OK, {"成品.md": line}, led)["w4"]["ok"], line


# ---------------------------------------------------------------------------
# 十二、P8：被時限切掉的那一次是「未判」，不是四個錯；整跑預算
# ---------------------------------------------------------------------------

def test_p8_timeout_label_is_pinned_to_the_contract():
    assert gg.TIMEOUT_LABEL == tv.GATE_CHECK_TIMEOUT_LABEL
    assert [c["ok"] for c in gg.timeout_checks()] == [None] * 4
    assert twinagent.RUN_BUDGET_S == 420.0 and twinagent.MIN_ATTEMPT_S == 60.0


def test_p8_contract_accepts_null_checks_only_for_the_timeout_label():
    nul = [{"id": f"G{i}", "ok": None, "label": tv.GATE_CHECK_TIMEOUT_LABEL} for i in (1, 2, 3, 4)]
    ok = _tv_cell(gate_checks=nul, passed=False, accepted=False, stop="attempts_exhausted")
    assert tv.validate(ok, require_task_kind=True) == []
    bad_label = [dict(nul[0], label="沒過")] + nul[1:]
    assert any("只准用於時間到" in b for b in tv.validate(
        _tv_cell(gate_checks=bad_label, passed=False, accepted=False, stop="attempts_exhausted"),
        require_task_kind=True))
    with_line = [dict(nul[0], file="plan", line=3)] + nul[1:]
    assert any("只准用於時間到" in b for b in tv.validate(
        _tv_cell(gate_checks=with_line, passed=False, accepted=False, stop="attempts_exhausted"),
        require_task_kind=True))
    # passed 必須是 false（null 不算通過）
    assert any("passed 與 checks" in b for b in tv.validate(
        _tv_cell(gate_checks=nul, passed=True), require_task_kind=True))


def test_p8_folder_turns_a_timed_out_attempt_into_null_checks_and_leaves_others_alone():
    lc = _lifecycle_two_attempts()
    for e in lc:
        if e["type"] == "agent_exited" and e["attempt"] == 1:
            e["timed_out"] = True
    ok = [{"id": "G1", "ok": True, "label": "讀過了"}, {"id": "G2", "ok": True, "label": "找得到出處"}]
    # 第 1 次被砍：沒有旁註；第 2 次有
    out = le.fold(sidecarlib.merge(lc, [_gate_row(2, ok, ts=11)]), verify_url="/r/{cell}")
    g = {e["attempt"]: e for e in out if e["type"] == "gate_ran"}
    assert [c["ok"] for c in g[1]["checks"]] == [None] * 4
    assert {c["label"] for c in g[1]["checks"]} == {tv.GATE_CHECK_TIMEOUT_LABEL}
    assert g[2]["checks"] == ok                      # 負控制：沒逾時的照常判
    assert tv.validate(out, require_task_kind=True) == []
    # 沒逾時時第 1 次沒有旁註 ⇒ 不帶 checks（不猜），不會變成 null
    out2 = le.fold(_lifecycle_two_attempts(), verify_url="/r/{cell}")
    assert all("checks" not in e for e in out2 if e["type"] == "gate_ran")


def test_p8_folder_cut_flag_on_the_sidecar_row_also_means_unjudged():
    row = dict(_gate_row(1, [{"id": "G1", "ok": False, "label": "x"}]), cut=True)
    assert sidecarlib.validate([row]) == []
    assert sidecarlib.validate([dict(row, cut=False)])
    out = le.fold(sidecarlib.merge(_lifecycle_two_attempts(), [row]), verify_url="/r/{cell}")
    g1 = next(e for e in out if e["type"] == "gate_ran")
    assert [c["ok"] for c in g1["checks"]] == [None]


def test_p8_e2e_killed_attempt_is_unjudged_in_events_and_phone_review(tmp_path, monkeypatch):
    script, *_ = _scenario(tmp_path)
    script["attempts"][1]["sleep"] = 30
    _install_fake_pi(tmp_path, monkeypatch, script)
    cfg = twinagent.AgentConfig(
        work_root=tmp_path / "work", events_path=tmp_path / "live.jsonl", model="m",
        endpoint="http://127.0.0.1:9/v1", parallel=1, timeout_s=6.0, requires=[])
    res = twinagent.run_one(twinagent.Job(SUB, TRAITS, cfg))
    evs = _evs(cfg)
    assert [e["timed_out"] for e in evs if e["type"] == "agent_exited"][:2] == [False, True]
    out = le.fold(sidecarlib.merge(evs, sidecarlib.read(sidecarlib.sidecar_path(cfg.events_path))),
                  verify_url="/r/{cell}")
    g = {e["attempt"]: e for e in out if e["type"] == "gate_ran"}
    assert [c["ok"] for c in g[1]["checks"]] == [False, False, True, False]           # 沒逾時：照判
    assert [c["ok"] for c in g[2]["checks"]] == [None] * 4                             # 逾時：未判
    assert tv.validate(out, require_task_kind=True) == []
    rv = res["review"]
    assert [r["ok"] for r in rv if r["attempt"] == 1] == [None] * 4
    assert {r["label"] for r in rv if r["attempt"] == 1} == {gg.TIMEOUT_LABEL}
    assert [r["ok"] for r in rv if r["attempt"] == 0] == [False, False, True, False]


def test_p8_attempt_limit_is_min_of_cap_and_what_is_left(tmp_path):
    rd = tmp_path
    import time as _t
    (rd / gg.GATE_META_NAME).write_text(json.dumps({
        "deadline_ts": _t.time() + 200, "attempt_cap_s": 300, "min_attempt_s": 60}), encoding="utf-8")
    assert 195 <= int(gg.attempt_limit(rd, False)) <= 200          # 剩 200 < 單次上限 300
    (rd / gg.GATE_META_NAME).write_text(json.dumps({
        "deadline_ts": _t.time() + 1000, "attempt_cap_s": 300, "min_attempt_s": 60}), encoding="utf-8")
    assert gg.attempt_limit(rd, True) == "300"                    # 預算夠：單次上限
    (rd / gg.GATE_META_NAME).write_text(json.dumps({
        "deadline_ts": _t.time() + 30, "attempt_cap_s": 300, "min_attempt_s": 60}), encoding="utf-8")
    assert gg.attempt_limit(rd, True) == "SKIP"                    # 重改、剩不到 60 秒
    assert gg.attempt_limit(rd, False) != "SKIP"                   # 第 1 次一定跑
    (rd / gg.GATE_META_NAME).unlink()
    assert gg.attempt_limit(rd, True) == "0"                       # 沒設預算＝不限（舊呼叫）


def test_p8_run_limited_kills_the_whole_group_and_returns_124():
    import time as _t
    t0 = _t.time()
    assert gg.run_limited(1, [sys.executable, "-c", "import time; time.sleep(30)"]) == 124
    assert _t.time() - t0 < 10
    assert gg.run_limited(5, [sys.executable, "-c", "import sys; sys.exit(3)"]) == 3


def test_p8_e2e_run_budget_caps_each_attempt_and_stops_opening_new_ones(tmp_path, monkeypatch):
    """預算 20 秒、重改下限 8 秒：第 1 次睡 14 秒做完（沒過）；剩 ~5 秒 < 8 ⇒ 第 2、3 次不開 pi，照 attempts_exhausted 收尾。"""
    script, *_ = _scenario(tmp_path)
    script["attempts"] = [dict(script["attempts"][0], sleep=14)]
    log = _install_fake_pi(tmp_path, monkeypatch, script)
    cfg = twinagent.AgentConfig(
        work_root=tmp_path / "work", events_path=tmp_path / "live.jsonl", model="m",
        endpoint="http://127.0.0.1:9/v1", parallel=1, timeout_s=60.0, requires=[],
        run_budget_s=20.0, min_attempt_s=8.0)
    res = twinagent.run_one(twinagent.Job(SUB, TRAITS, cfg))
    sm = res["summary"]
    assert sm["stop_reason"] == "attempts_exhausted" and sm["accepted"] is False
    pl = [json.loads(l) for l in log.read_text().splitlines()]
    assert [p["stage"] for p in pl] == [1, 2], "第 2、3 次不該再開 pi"
    evs = _evs(cfg)
    assert [e["type"] for e in evs if e["type"] == "agent_exited"] and \
        [e["timed_out"] for e in evs if e["type"] == "agent_exited"] == [False, False, False]
    ws, rd = twinagent.paths_for(cfg.work_root, SUB)
    assert json.loads((rd / gg.CUT_NAME).read_text()) == [2, 3]
    rv = res["review"]
    assert [r["ok"] for r in rv if r["attempt"] == 0] == [False, False, True, False]
    assert all(r["ok"] is None for r in rv if r["attempt"] in (1, 2))
    out = le.fold(sidecarlib.merge(evs, sidecarlib.read(sidecarlib.sidecar_path(cfg.events_path))),
                  verify_url="/r/{cell}")
    g = {e["attempt"]: e for e in out if e["type"] == "gate_ran"}
    assert all(c["ok"] is None for a in (2, 3) for c in g[a]["checks"])
    assert tv.validate(out, require_task_kind=True) == []
    # 負控制：預算夠大時同一份腳本照樣開第 2 次
    log.unlink()
    cfg2 = twinagent.AgentConfig(
        work_root=tmp_path / "work2", events_path=tmp_path / "live2.jsonl", model="m",
        endpoint="http://127.0.0.1:9/v1", parallel=1, timeout_s=60.0, requires=[],
        run_budget_s=400.0, min_attempt_s=6.0)
    twinagent.run_one(twinagent.Job(SUB, TRAITS, cfg2))
    assert [json.loads(l)["stage"] for l in log.read_text().splitlines()].count(2) == 3


def test_w1_two_failure_kinds_have_two_messages_and_labels_same_id(tmp_path):
    plan = "x\n\n它牽動到：\n- 地上/帳本鏈/不存在的檔.txt\n- 地上/紙卡地/格狀圖.txt\n步驟：\n1. y\n"
    res = run_gate(tmp_path, plan, {}, ledger([CHAIN], ground_files=GF))
    msgs = dict((l, m) for l, m in only(res, "w1"))
    assert msgs[4].endswith("地上沒有這個檔") and "地上有" not in msgs[4]
    assert "地上有，這一跑沒有成功打開過" in msgs[5]
    assert gg.describe("check_w1_read", False, msgs[4]) == ("G1", "點名的東西地上沒有（計畫第 4 行）")
    assert gg.describe("check_w1_read", False, msgs[5]) == ("G1", "點名的東西沒打開（計畫第 5 行）")
    # 負控制：地上有的檔讀過就過；地上沒有的檔怎麼讀都不會過
    assert run_gate(tmp_path, plan.replace("- 地上/帳本鏈/不存在的檔.txt\n", ""), {}, ledger([GRID], ground_files=GF))["w1"]["ok"]
    led = ledger([GRID], ground_files=GF)
    led["read"].append("地上/帳本鏈/不存在的檔.txt")          # 步驟紀錄說「讀過」也沒用：地上沒有這個檔
    assert not run_gate(tmp_path, plan, {}, led)["w1"]["ok"]
    for m in msgs.values():
        assert_ks1_clean(m)


# ---------------------------------------------------------------------------
# 十三、P9：圍牆裡的閘門旁註（圍牆裡只寫得到 run-dir，主機側 EventForwarder 轉出來）
# ---------------------------------------------------------------------------

def test_p9_enclosed_gate_rows_are_forwarded_before_the_lifecycle_lines(tmp_path):
    from ops.exhibit.twin import twinenclose
    caller = {"cell_id": "tw-1", "resident": "X", "task_kind": "practical"}
    part, gpart = tmp_path / "part.jsonl", tmp_path / "gpart.jsonl"
    dst = tmp_path / "live.jsonl"
    base = {"schema": lifecycle.SCHEMA, "run_id": "R", "task_id": "twin:tw-1", "arm": "RUN-ON"}
    part.write_text(json.dumps({**base, "type": "gate_ran", "seq": 1, "ts_ms": 5, "attempt": 1, "passed": False,
                                "n_passed": 3, "n_tests": 4, "failed_case": "x", "verdict_sha256": "v"}) + "\n",
                    encoding="utf-8")
    good = _gate_row(1, [{"id": "G1", "ok": True, "label": "讀過了"}], rid="R")
    wrong_cell = dict(good, cell_id="tw-9")
    wrong_type = dict(good, type="twin_say")
    gpart.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in (good, wrong_cell, wrong_type)),
                     encoding="utf-8")
    f = twinenclose.EventForwarder(part, dst, task_id="twin:tw-1", caller=caller, gate_src=gpart,
                                   gate_dst=sidecarlib.sidecar_path(dst))
    f._pump()
    rows = sidecarlib.read(sidecarlib.sidecar_path(dst))
    assert [r["type"] for r in rows] == ["twin_gate"] and rows[0]["cell_id"] == "tw-1"   # 負控制：別格、別型別不轉
    assert f.gate_forwarded == 1 and f.forwarded == 1
    # 沒設 gate_src 的舊呼叫：不轉旁註
    dst2 = tmp_path / "live2.jsonl"
    f2 = twinenclose.EventForwarder(part, dst2, task_id="twin:tw-1", caller=caller)
    f2._pump()
    assert not sidecarlib.sidecar_path(dst2).exists()


def test_p9_enclosed_run_points_the_gate_meta_at_run_dir_files(tmp_path, monkeypatch):
    from ops.exhibit.twin import twinenclose
    script, *_ = _scenario(tmp_path)
    _install_fake_pi(tmp_path, monkeypatch, script)
    monkeypatch.setattr(twinagent, "use_enclosure", lambda cfg: (True, "ok"))
    seen = {}

    def fake(**kw):
        seen.update(kw)
        raise RuntimeError("stop")
    monkeypatch.setattr(twinenclose, "run_enclosed", fake)
    cfg = twinagent.AgentConfig(
        work_root=tmp_path / "work", events_path=tmp_path / "live.jsonl", model="m",
        endpoint="http://127.0.0.1:9/v1", parallel=1, timeout_s=60.0, requires=[], enclose="on")
    twinagent.run_one(twinagent.Job(SUB, TRAITS, cfg))
    ws, rd = twinagent.paths_for(cfg.work_root, SUB)
    meta = json.loads((rd / gg.GATE_META_NAME).read_text(encoding="utf-8"))
    assert meta["events_path"] == str(rd / twinenclose.EVENTS_PART)
    assert meta["sidecar_path"] == str(rd / twinenclose.GATE_SIDECAR_PART)
    assert meta["deadline_ts"] > 0 and meta["attempt_cap_s"] == 60.0 and meta["min_attempt_s"] == 60.0
    assert seen["gate"]["retry_arm"] == "revise" and seen["gate"]["suite_dir"] == str(rd / gg.TESTS_DIRNAME)


def test_p9_budget_env_overrides_and_garbage_falls_back(monkeypatch):
    kw = dict(work_root=pathlib.Path("/x"), events_path=None, model="m", endpoint="e")
    monkeypatch.setenv("VACANT_TWIN_RUN_BUDGET_S", "33")
    monkeypatch.setenv("VACANT_TWIN_MIN_ATTEMPT_S", "7")
    c = twinagent.AgentConfig(**kw)
    assert (c.run_budget_s, c.min_attempt_s) == (33.0, 7.0)
    monkeypatch.setenv("VACANT_TWIN_RUN_BUDGET_S", "abc")
    monkeypatch.setenv("VACANT_TWIN_MIN_ATTEMPT_S", "-1")
    c = twinagent.AgentConfig(**kw)
    assert (c.run_budget_s, c.min_attempt_s) == (twinagent.RUN_BUDGET_S, twinagent.MIN_ATTEMPT_S)


def test_p9_a_cut_attempt_that_still_passed_keeps_its_real_checks():
    lc = _lifecycle_two_attempts()
    for e in lc:
        if e["type"] == "agent_exited" and e["attempt"] == 2:
            e["timed_out"] = True                       # 第 2 次被砍，但閘門判過了（gate_ran.passed=true）
    ok = [{"id": "G1", "ok": True, "label": "讀過了"}, {"id": "G2", "ok": True, "label": "找得到出處"}]
    out = le.fold(sidecarlib.merge(lc, [_gate_row(2, ok, ts=11)]), verify_url="/r/{cell}")
    g2 = next(e for e in out if e["type"] == "gate_ran" and e["attempt"] == 2)
    assert g2["passed"] is True and g2["checks"] == ok
    assert tv.validate(out, require_task_kind=True) == []
