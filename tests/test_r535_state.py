"""`ops/gain/r535/state_r535.py` 的紅線（R535 收官判定器）。

這支在架構裡承重什麼：**狀態表判錯不會噴錯**——它會照樣吐出一個看起來很像
結論的字串，而「方向反了」與「方向對了」在那份 JSON 裡長得一模一樣。
R532 的 AMEND1 就是這樣把一個負向顯著的結果貼成 `EFFECTIVE`。

所以每一種壞法都要有一條跑得到的紅線，而且**每一條都附負向控制**：
把對應那一行判定式拿掉（`disabled={...}`），該條測試必須翻紅。
沒有負控的「全綠」跟把判定關掉在輸出上同形。

十一條紅線：

  1. RF 贏 ⇒ `CONFIRMED_NEGATIVE`，**不是** `POSITIVE`；
  2. RF **>** RS 顯著且 `m7_ws > 0` ⇒ `STALE_WORKSPACE_EFFECT(+)`，**不是** `BREACH`；
  3. RF ≠ RS 顯著且 `m7_ws = 0`、解析器 `--selftest` 綠 ⇒ `MECHANISM_BREACH`；
  4. PC 的 attempt-1 **不准**混進觸發率分母；
  5. `m7_file` 的 `null` **不可以**被當成 `false` 算進分母；
  6. 求值順序：同時滿足 `NOT_TRIGGERED` 與 `CONFIRMED_POSITIVE` ⇒ 前者；
  7. b/c 方向（b ≡ RF 的 M1=0 ∧ RP 的 M1=1 ＝ RP 贏），並與
     `research.discordance` 對算；
  8. `M1`（accepted ∧ hidden）與 `M1_vis`（accepted）方向相反 ⇒ H1 走 `M1`；
  9. 拒交但凍結快照 hidden 全過 ⇒ 該格 `M1` **必須是 0**；
 10. `M1_vis` 贏而 `M1` 不顯著 ⇒ 分歧句連 `M6` 一起印出來；
 11. RF **<** RS 顯著且 `m7_ws > 0` ⇒ `STALE_WORKSPACE_EFFECT(−)`，**不是** `BREACH`
     （2026-09-19 護欄表換版：方向不再進判準，兩個符號都走同一支）。

另外：`--mutation-check` 整張表要全綠、口徑禁語要掃得到、
「拿不到 `m7_ws` 解析器的 `--selftest` 結果」**不可以**被當成綠。
"""

from __future__ import annotations

import json
import pathlib
import sys
from dataclasses import dataclass

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ops.gain.r535.state_r535 import (  # noqa: E402
    ALPHA, BANNED, CHAIN_ORDER, FAMILY, M7_FILE_BREACH, TRIGGER_ARMS,
    analyse, apply_m1, bc_counts, check_diction, fixture, main,
    mutation_check, normalise_cell, read_m7ws_selftest, selftest,
    trigger_rate,
)
from vacant_network.research import discordance  # noqa: E402

OFF = frozenset


def s1(doc: dict) -> str:
    return doc["state"]["S1"]


def ctrl(doc: dict) -> str | None:
    return doc["control"]["S1"]["state"]


# ── 1. RF 贏 ⇒ CONFIRMED_NEGATIVE，不是 POSITIVE ──────────────────────────

def test_rf_wins_is_confirmed_negative_not_positive():
    """R532 AMEND1 的那一格：負向顯著**不准**被貼成正向。"""
    doc = analyse(fixture("rf_wins"))
    h1 = doc["per_stratum"]["S1"]["h1"]
    assert h1["c"] > h1["b"], "樣本本身要是 RF 贏（c > b）"
    assert s1(doc) == "CONFIRMED_NEGATIVE"
    assert s1(doc) != "CONFIRMED_POSITIVE"
    # 收官句要說「低」不是「高」
    assert "**低**" in doc["closing"]["S1"]


def test_rf_wins_negative_control_removing_the_rule_flips_it():
    """拿掉 `CONFIRMED_NEGATIVE` 那一行 ⇒ 掉出這一格（求值順序往下走）。"""
    off = analyse(fixture("rf_wins"), disabled=OFF({"CONFIRMED_NEGATIVE"}))
    assert s1(off) != "CONFIRMED_NEGATIVE"


def test_negative_direction_guard_is_what_keeps_rf_wins_out_of_positive():
    """把**方向**護欄拿掉 ⇒ RF 贏的資料會被貼成 `CONFIRMED_POSITIVE`。

    這一條在證明「顯著」本身擋不住方向錯誤——擋住的是那個 `b > c`。
    """
    off = analyse(fixture("rf_wins"), disabled=OFF({"POS_DIRECTION"}))
    assert s1(off) == "CONFIRMED_POSITIVE"


# ── 2/3/11. 控制鏈（2026-09-19 護欄表換版）────────────────────────────────

def test_rf_gt_rs_with_stale_workspace_is_a_signed_stale_not_a_breach():
    """RF **>** RS 顯著、`M7_file = 0`、**`M7_ws > 0`** ⇒ 髒工作區被摸過。

    描述性狀態、**帶符號**、**不凍結任何句子**；判成 `MECHANISM_BREACH` 是假警報。
    """
    doc = analyse(fixture("rf_gt_rs_stale"), m7ws_selftest="green")
    assert ctrl(doc) == "STALE_WORKSPACE_EFFECT(+)"
    assert doc["control"]["S1"]["sign"] == "+"
    assert doc["mechanism_breach_any_stratum"] is False
    assert doc["control"]["S1"]["rf_gt_rs"] is True


def test_rf_lt_rs_with_stale_workspace_is_also_stale_not_a_breach():
    """**第 11 條**：RF **<** RS 顯著且 `M7_ws > 0` ⇒ `STALE_WORKSPACE_EFFECT(−)`。

    舊表把 `RF < RS 顯著` 直接判 `MECHANISM_BREACH`。那一列已經撤掉：
    模型看到自己上一份錯碼會**錨定在上面**，`resample` 重置工作區反而拿到
    乾淨的重抽 ⇒ 「保留工作區」的效果**兩個符號都可能**，方向不再進判準。
    """
    doc = analyse(fixture("rs_gt_rf_stale"), m7ws_selftest="green")
    assert ctrl(doc) == "STALE_WORKSPACE_EFFECT(−)"
    assert ctrl(doc) != "MECHANISM_BREACH"
    assert doc["control"]["S1"]["sign"] == "−"
    assert doc["control"]["S1"]["rf_lt_rs"] is True
    assert doc["mechanism_breach_any_stratum"] is False


def test_both_signs_go_through_the_same_branch():
    """兩個符號走同一支：只差在 `sign`，狀態名前綴一樣。"""
    plus = ctrl(analyse(fixture("rf_gt_rs_stale"), m7ws_selftest="green"))
    minus = ctrl(analyse(fixture("rs_gt_rf_stale"), m7ws_selftest="green"))
    assert plus.startswith("STALE_WORKSPACE_EFFECT")
    assert minus.startswith("STALE_WORKSPACE_EFFECT")
    assert plus != minus


def test_ws_zero_with_green_selftest_is_a_breach():
    """RF ≠ RS 顯著、`M7_ws = 0`、解析器 `--selftest` **綠** ⇒ `BREACH`。"""
    doc = analyse(fixture("rf_gt_rs_nostale"), m7ws_selftest="green")
    assert ctrl(doc) == "MECHANISM_BREACH"
    assert doc["mechanism_breach_any_stratum"] is True
    assert "負控制異常，機制待查" in doc["closing"]["S1"]


@pytest.mark.parametrize("gate", ["red", "unavailable"])
def test_ws_zero_without_a_green_selftest_invalidates_the_instrument(gate):
    """selftest 紅／拿不到 ⇒ **`M7_ws` 這個指標判 `INVALID`**，不是 breach。

    「量具壞了」與「機制壞了」在數字上同形，所以這一格不准猜。
    ⚠ 它只作廢 `M7_ws`，不作廢 H1、不作廢該層。
    """
    doc = analyse(fixture("rf_gt_rs_nostale"), m7ws_selftest=gate)
    assert ctrl(doc) == "M7_WS_INVALID"
    assert doc["mechanism_breach_any_stratum"] is False
    assert s1(doc) != "INVALID", "只作廢 M7_ws，不作廢該層"
    assert "量具壞了" in " ".join(doc["control"]["S1"]["reasons"])


def test_missing_selftest_is_never_green():
    """負向控制：拿掉那道閘 ⇒ 同一份資料被判成 `MECHANISM_BREACH`（假警報）。"""
    off = analyse(fixture("rf_gt_rs_nostale"), m7ws_selftest="unavailable",
                  disabled=OFF({"M7WS_SELFTEST_GATE"}))
    assert ctrl(off) == "MECHANISM_BREACH"


def test_selftest_reader_never_defaults_to_green(tmp_path):
    """讀不到、看不懂、檔案不在 ⇒ 一律 `unavailable`，**不是** `green`。"""
    assert read_m7ws_selftest(None)["result"] == "unavailable"
    assert read_m7ws_selftest(tmp_path / "nope.json")["result"] == "unavailable"
    junk = tmp_path / "junk.txt"
    junk.write_text("誰知道呢", encoding="utf-8")
    assert read_m7ws_selftest(junk)["result"] == "unavailable"
    for payload, want in (('{"ok": true}', "green"), ('{"ok": false}', "red"),
                          ('{"verdict": "OK"}', "green"),
                          ('{"all_ok": false}', "red"), ("green", "green"),
                          ("red", "red"), ('{"note": "hi"}', "unavailable")):
        f = tmp_path / "s.json"
        f.write_text(payload, encoding="utf-8")
        assert read_m7ws_selftest(f)["result"] == want, payload


@pytest.mark.parametrize("kind,key,gate,want", [
    ("rf_gt_rs_stale", "STALE_WS", "green", "STALE_WORKSPACE_EFFECT(+)"),
    ("rs_gt_rf_stale", "STALE_WS", "green", "STALE_WORKSPACE_EFFECT(−)"),
    ("rf_gt_rs_nostale", "BREACH_WS_ZERO", "green", "MECHANISM_BREACH"),
])
def test_control_chain_negative_control(kind, key, gate, want):
    assert ctrl(analyse(fixture(kind), m7ws_selftest=gate)) == want
    assert ctrl(analyse(fixture(kind), m7ws_selftest=gate,
                        disabled=OFF({key}))) is None


def test_the_control_states_are_mutually_exclusive():
    """互斥：同一層只會落在其中一個。"""
    for kind in ("rf_gt_rs_stale", "rs_gt_rf_stale", "rf_gt_rs_nostale",
                 "m7_null_not_false"):
        st = ctrl(analyse(fixture(kind), m7ws_selftest="green"))
        assert st in (None, "MECHANISM_BREACH", "M7_WS_INVALID",
                      "STALE_WORKSPACE_EFFECT(+)", "STALE_WORKSPACE_EFFECT(−)")


def test_stale_closing_line_is_its_own_paragraph_and_cites_m7_ws_solution():
    """`STALE_WORKSPACE_EFFECT(±)` 的句子**不接在 H1 句後**，且必須引 M7_ws_solution。"""
    doc = analyse(fixture("rs_gt_rf_stale"), m7ws_selftest="green")
    line = doc["closing_control"]["S1"]
    assert line is not None
    assert line not in doc["closing"]["S1"], "不准接在 H1 收官句後面"
    assert "M7_ws_solution=" in line and "M7_file=0" in line
    assert "未經家族校正" in line
    assert "不得讀成 revise 與 resample 的優劣結論" in line
    assert "與本輪主問題（回饋走哪條管道）無關" in line
    assert "少交付並通過隱藏測資" in line, "符號要落在「多／少」上"
    assert "逐題工具序列見" in line


def test_stale_line_is_rewritten_when_the_workspace_was_never_read():
    """`M7_ws_solution == 0` 而 RF ≠ RS 顯著 ⇒ 「被 `ls` 到但沒被讀、來源未定」。"""
    doc = analyse(fixture("rs_gt_rf_stale_unread"), m7ws_selftest="green")
    line = doc["closing_control"]["S1"]
    assert "差異來源未定" in line and "沒被讀" in line
    read = analyse(fixture("rs_gt_rf_stale"),
                   m7ws_selftest="green")["closing_control"]["S1"]
    assert "差異來源未定" not in read


def test_m7_ws_solution_is_never_in_the_decision():
    """它是收官句的證據，**不進判準**；null 不進分母。"""
    ps = analyse(fixture("rf_gt_rs_stale"),
                 m7ws_selftest="green")["per_stratum"]["S1"]
    ms = ps["m7_ws_solution"]
    assert ms["in_decision"] is False
    assert ms["rate"] == 1.0 and ms["n_measured"] == 50
    trail = json.dumps(ps["decision"]["trail"], ensure_ascii=False)
    assert "m7_ws_solution" not in trail


def test_h1_is_unaffected_by_the_workspace_effect():
    """RP 與 RF 都是 `revise` ⇒ 保留工作區的效果在 H1 的配對裡對消。"""
    for kind in ("rf_gt_rs_stale", "rs_gt_rf_stale"):
        doc = analyse(fixture(kind), m7ws_selftest="green")
        h1 = doc["per_stratum"]["S1"]["h1"]
        assert (h1["b"], h1["c"]) == (0, 0), "兩臂逐題相同 ⇒ 沒有不一致對"
        assert "對消" in doc["control"]["S1"]["h1_unaffected"]


def test_h2_always_prints_its_interval_even_when_not_significant():
    """護欄表第 4 列：不顯著也要印 (b,c)、p、95% 區間、TOST、三個 M7。"""
    # RS 與 RF 逐題相同的樣本 ⇒ H2 必定不顯著
    ps = analyse(fixture("pc_pollutes_trigger"))["per_stratum"]["S1"]
    assert ps["h2_control"]["p_exact"] >= ALPHA
    assert ps["h2_ci"]["ci_hi"] is not None
    for k in ("m7_file", "m7_ws", "m7_ws_solution", "tost"):
        assert k in ps


# ── 4. PC 的 attempt-1 不准混進觸發率分母 ──────────────────────────────────

def test_pc_attempt1_must_not_enter_the_trigger_denominator():
    """PC 的工作區是 `TASK_explicit.md`＝另一個 TASK。

    混進來會把失敗率往下拉 ⇒ `NOT_TRIGGERED` 假觸發 ⇒ 整層被判「題庫沒做出窗口」。
    """
    cells = apply_m1(fixture("pc_pollutes_trigger"))
    good = trigger_rate(cells, "S1")
    bad = trigger_rate(cells, "S1", include_pc=True)
    assert good["arms"] == list(TRIGGER_ARMS) and "PC" not in good["arms"]
    assert good["n"] == 150 and bad["n"] == 200
    assert good["attempt1_fail_rate"] >= good["threshold"]
    assert bad["attempt1_fail_rate"] < bad["threshold"], "樣本要能把門檻拉過去"


def test_pc_pollution_negative_control_flips_the_state():
    """負向控制：把 PC 混進分母 ⇒ 狀態翻成 `NOT_TRIGGERED`（假觸發）。"""
    assert s1(analyse(fixture("pc_pollutes_trigger"))) != "NOT_TRIGGERED"
    off = analyse(fixture("pc_pollutes_trigger"),
                  disabled=OFF({"TRIGGER_EXCLUDES_PC"}))
    assert s1(off) == "NOT_TRIGGERED"


# ── 5. `m7_file` 的 null 不可以被當成 false ───────────────────────────────

def test_m7_file_null_is_not_false():
    """沒量到 ≠ 量到 0（鐵律 3 的 `infra_void` 同一條）。

    樣本：20 格 RF，2 格量到且命中、18 格 `null`（沒有第 2 次嘗試）。
    正確分母是 2 ⇒ 1.0 > 10% ⇒ `MECHANISM_BREACH`；
    把 `null` 當 `false` ⇒ 2/20 = 0.10，**不** > 0.10 ⇒ 漏掉。
    """
    doc = analyse(fixture("m7_null_not_false"), m7ws_selftest="green")
    mf = doc["per_stratum"]["S1"]["m7_file"]
    assert mf["null"] == 18 and mf["n_measured"] == 2
    assert mf["denominator"] == 2 and mf["rate"] == 1.0
    assert mf["rate"] > M7_FILE_BREACH
    assert ctrl(doc) == "MECHANISM_BREACH"


def test_m7_file_null_negative_control():
    off = analyse(fixture("m7_null_not_false"), m7ws_selftest="green",
                  disabled=OFF({"M7_NULL_NOT_FALSE"}))
    mf = off["per_stratum"]["S1"]["m7_file"]
    assert mf["denominator"] == 20 and mf["rate"] == pytest.approx(0.10)
    assert ctrl(off) is None, "把 null 當 false 就會漏掉這個 breach"


def test_m7_file_reports_the_hole_it_cannot_measure():
    """有第 ≥2 次嘗試卻量不到的格數要印出來，不是靜靜地不算。"""
    mf = analyse(fixture("m7_null_not_false"),
                 m7ws_selftest="green")["per_stratum"]["S1"]["m7_file"]
    assert "n_retried_unmeasured" in mf
    assert mf["n_retried_unmeasured"] == 0   # 本樣本的 null 都是沒重試


# ── 6. 求值順序 ───────────────────────────────────────────────────────────

def test_evaluation_order_not_triggered_beats_confirmed_positive():
    """同時滿足兩者的資料 ⇒ 出 `NOT_TRIGGERED`（鏈上比較早的那一個）。"""
    doc = analyse(fixture("order_not_triggered_beats_positive"))
    assert s1(doc) == "NOT_TRIGGERED"
    # 證明它**真的**同時滿足 CONFIRMED_POSITIVE：把前面那一條拿掉就掉進去
    off = analyse(fixture("order_not_triggered_beats_positive"),
                  disabled=OFF({"NOT_TRIGGERED"}))
    assert s1(off) == "CONFIRMED_POSITIVE"


def test_chain_order_is_frozen():
    assert CHAIN_ORDER == (
        "INVALID", "NOT_TRIGGERED", "CEILING_TOO_LOW", "CONFIRMED_POSITIVE",
        "CONFIRMED_NEGATIVE", "RULED_OUT", "INCONCLUSIVE")
    trail = analyse(fixture("rp_wins"))["per_stratum"]["S1"]["decision"]["trail"]
    assert [t["state"] for t in trail] == list(CHAIN_ORDER[:4])


def test_invalid_is_evaluated_first():
    """`--reconcile` 判 INVALID ⇒ 蓋過底下每一條，連 RP 大勝都不例外。"""
    doc = analyse(fixture("rp_wins"), reconcile_invalid=True)
    assert s1(doc) == "INVALID" and doc["state"]["S2"] == "INVALID"


# ── 7. b/c 方向（陷阱一）─────────────────────────────────────────────────

def test_bc_direction_rp_wins_gives_b_gt_c():
    """凍結：`b ≡ RF 的 M1 = 0 ∧ RP 的 M1 = 1`（＝RP 贏）。

    ⚠ 預註冊 §六-2 第 4 列寫的是 `c > b`＝RP 贏——**字母鏡像**。
    這一條斷言的是 `b > c`，不是相反。
    """
    cells = apply_m1(fixture("rp_wins"))
    r = bc_counts(cells, arm_a="RF", arm_b="RP", field="m1")
    assert r["b"] == 14 and r["c"] == 0
    assert r["b"] > r["c"], "RP 明顯贏 ⇒ b > c（不是 c > b）"
    assert r["direction"] == "RP>RF"


def test_bc_direction_matches_research_discordance():
    """直接拿 `research.discordance` 對算——它哪天改方向，這條先紅。

    `discordance` 只認 `.passed_gt`，所以這裡把 M1 塞進那個欄位再比對；
    比的是**方向約定**（哪個字母代表誰贏），不是「本檔可以改用它」。
    """
    @dataclass
    class Item:
        passed_gt: bool

    cells = apply_m1(fixture("rp_wins"))
    by_task: dict[str, dict] = {}
    for c in cells:
        by_task.setdefault(c["task_id"], {})[c["arm"]] = Item(bool(c["m1"]))
    results = [v for _, v in sorted(by_task.items())]
    b_ref, c_ref, _ = discordance(results, arm_a="RF", arm_b="RP")
    ours = bc_counts(cells, arm_a="RF", arm_b="RP", field="m1")
    assert (b_ref, c_ref) == (ours["b"], ours["c"])
    assert b_ref > c_ref


def test_h2_uses_the_same_letter_convention():
    """H2 ＝ `discordance(results, arm_a="RS", arm_b="RF")` ⇒ b2 ＝ RF 贏。"""
    doc = analyse(fixture("rf_gt_rs_nostale"))
    h2 = doc["per_stratum"]["S1"]["h2_control"]
    assert h2["arm_a"] == "RS" and h2["arm_b"] == "RF"
    assert h2["b"] > h2["c"] and doc["control"]["S1"]["rf_gt_rs"] is True


# ── 8. M1 vs M1_vis（H1 走 M1）────────────────────────────────────────────

def test_h1_uses_m1_not_accepted_only():
    """`M1_vis` 說 RP 贏 15、`M1` 說 RF 贏 10 ⇒ H1 必須走 `M1`。

    accepted-only 會把「針對可見 case 打補丁（過閘門、隱藏不過）」算成交付，
    那是 `revise` 相對 `resample` 的可預期灌水方向。
    """
    ps = analyse(fixture("vis_vs_m1_opposite"))["per_stratum"]["S1"]
    assert ps["h1"]["field"] == "m1"
    assert (ps["h1"]["b"], ps["h1"]["c"]) == (0, 10)
    assert (ps["m1_vis_paired"]["b"], ps["m1_vis_paired"]["c"]) == (15, 0)
    assert ps["m1_vis_paired"]["in_family"] is False
    assert ps["m1_vis_paired"]["in_state_table"] is False
    assert ps["m1_vis_paired"]["ci"]["ci_hi"] is not None, "M1_vis 要印 95% 區間"
    assert s1(analyse(fixture("vis_vs_m1_opposite"))) == "CONFIRMED_NEGATIVE"


def test_h1_uses_m1_negative_control():
    """負向控制：讓 H1 改讀 accepted-only ⇒ 同一份資料翻成 `POSITIVE`。"""
    off = analyse(fixture("vis_vs_m1_opposite"), disabled=OFF({"H1_USES_M1"}))
    assert s1(off) == "CONFIRMED_POSITIVE"


def test_family_is_size_two_and_only_h1():
    doc = analyse(fixture("rp_wins"))
    assert doc["family"]["members"] == ["H1-S1", "H1-S2"]
    assert doc["family"]["size"] == 2 == len(FAMILY)
    assert len(doc["family"]["raw_p"]) == 2
    ps = doc["per_stratum"]["S1"]
    assert ps["h2_control"]["in_family"] is False
    assert ps["h3_descriptive"]["in_family"] is False
    assert ps["h3_descriptive"]["in_state_table"] is False


# ── 9. 拒交但快照 hidden 全過 ⇒ M1 = 0 ────────────────────────────────────

def test_refused_cell_scores_zero_even_if_hidden_passes():
    """一格拒交、凍結快照碰巧過了 hidden ⇒ `M1` 必須是 0，而且要標 inconsistent。

    `research.discordance` 在這裡會算成 1（它忽略 asserted／refused）——
    那正是不借用它的第二個理由。
    """
    cells = apply_m1(fixture("refused_but_hidden_passes"))
    bad = next(c for c in cells if c["cell"] == "s1_00__RP")
    assert bad["accepted"] is False and bad["hidden"] is True
    assert bad["m1"] is False, "拒交強制 0"
    assert bad["m1_vis"] is False
    assert bad["inconsistent"] is True
    ps = analyse(fixture("refused_but_hidden_passes"))["per_stratum"]["S1"]
    assert ps["inconsistent"]["n"] == 15
    assert "不准靜默計入" in ps["inconsistent"]["rule"]


def test_refused_negative_control_flips_the_state():
    """拿掉「M1 要求 accepted」⇒ 那 15 格被算成交付 ⇒ 結論翻掉。"""
    on = analyse(fixture("refused_but_hidden_passes"))
    off = analyse(fixture("refused_but_hidden_passes"),
                  disabled=OFF({"M1_REQUIRES_ACCEPTED"}))
    assert s1(on) == "CONFIRMED_NEGATIVE"
    assert s1(off) != "CONFIRMED_NEGATIVE"


def test_m1_is_accepted_and_hidden():
    """真值表寫死：只有兩個都 true 才算交付。"""
    rows = [
        {"status": "scored", "cell": "t__RP", "task_id": "t", "arm": "RP",
         "stratum": "S1", "visible_accepted": a, "hidden_pass": h,
         "by_attempt": [{"attempt": 1, "visible_accepted": a,
                         "hidden_pass": h}]}
        for a, h in ((True, True), (True, False), (False, True), (False, False))
    ]
    cells = apply_m1([normalise_cell(r) for r in rows])
    assert [c["m1"] for c in cells] == [True, False, False, False]
    assert [c["m1_vis"] for c in cells] == [True, True, False, False]
    assert [c["m6"] for c in cells] == [False, True, False, False]
    assert [c["inconsistent"] for c in cells] == [False, False, True, False]


# ── 10. 分歧句 ＋ M6 必印 ─────────────────────────────────────────────────

def test_divergence_line_fires_with_m6():
    """`M1_vis` 顯示 RP > RF 而 `M1` 不顯著 ⇒ 管道買到的是過閘門。"""
    doc = analyse(fixture("divergence_m6"))
    dv = doc["divergence"]["S1"]
    assert dv["m1_vis_shows_rp_gt_rf"] is True
    assert dv["m1_not_significant"] is True
    assert dv["fired"] is True
    assert dv["m6_rp_rate"] == pytest.approx(0.30)
    assert "管道買到的是過閘門，不是通過隱藏測資" in dv["line"]
    assert "M6 = 0.300" in dv["line"]
    assert dv["line"] in doc["closing"]["S1"]


def test_divergence_negative_control():
    off = analyse(fixture("divergence_m6"), disabled=OFF({"DIVERGENCE_NOTE"}))
    assert off["divergence"]["S1"]["fired"] is False


def test_m6_is_always_printed():
    """M6 必印——不管有沒有觸發分歧句，四臂都要有一格。"""
    for kind in ("rp_wins", "rf_wins", "divergence_m6"):
        m6 = analyse(fixture(kind))["per_stratum"]["S1"]["m6"]
        assert set(m6["by_arm"]) == {"RS", "RF", "RP", "PC"}
        for arm in ("RS", "RF", "RP", "PC"):
            assert "rate" in m6["by_arm"][arm]


# ── 口徑、TOST、分層、整張負控表 ─────────────────────────────────────────

def test_banned_words_never_appear_in_output():
    """「等價」兩個字任何輸出都不准出現。"""
    for kind in ("rp_wins", "rf_wins", "divergence_m6",
                 "refused_but_hidden_passes"):
        doc = analyse(fixture(kind))
        d = check_diction(doc)
        assert d["ok"], f"{kind} 命中禁語 {d['hits']}"
        assert "等價" in BANNED and "信任" in BANNED


def test_diction_check_has_teeth():
    """負向控制：掃描器要真的抓得到（零命中與把掃描關掉在輸出上同形）。"""
    assert check_diction({"x": "兩臂等價"})["ok"] is False
    assert check_diction({"x": "兩臂等價"})["hits"] == ["等價"]


def test_tost_decides_nothing():
    """TOST 只印不裁：它的結果不准出現在任何一條狀態判準裡。"""
    ps = analyse(fixture("rp_wins"))["per_stratum"]["S1"]
    assert ps["tost"]["decides_nothing"] is True
    assert ps["tost"]["verdict"].startswith("TOST（δ=15 pp）")
    assert ps["tost"]["reading"] in (
        "±15 pp 內未區分開", "本輪的 n 不足以在 ±15 pp 內宣告未區分開")
    trail_text = json.dumps(ps["decision"]["trail"], ensure_ascii=False)
    assert "TOST" not in trail_text and "tost" not in trail_text


def test_ruled_out_uses_the_one_sided_95_upper_bound():
    """`RULED_OUT` 吃的是 95% 區間**上緣**，不是 TOST。"""
    doc = analyse(fixture("rf_wins"), disabled=OFF({"CONFIRMED_NEGATIVE"}))
    ps = doc["per_stratum"]["S1"]
    assert s1(doc) == "RULED_OUT"
    assert ps["ci"]["ci_hi"] < 0.15
    assert "2.5/97.5" in ps["ci"]["method"]


def test_strata_are_reported_separately():
    """S1／S2 各自一個狀態，不合併。"""
    doc = analyse(fixture("rp_wins"))
    assert set(doc["state"]) == {"S1", "S2"}
    assert set(doc["per_stratum"]) == {"S1", "S2"}
    assert doc["state"]["S2"] in CHAIN_ORDER
    assert "不合併" in doc["report_rule"]


def test_selftest_and_mutation_table_are_green():
    """整張負向控制表：每一條判定式拿掉之後都必須翻紅。"""
    st = selftest()
    assert st["all_ok"], [c for c in st["checks"] if not c["ok"]]
    mc = mutation_check()
    assert mc["all_ok"], [r for r in mc["rows"] if not r["ok"]]
    for r in mc["rows"]:
        assert r["flipped"], f"{r['removed']} 拿掉之後結論沒變 ⇒ 它沒在跑"


def test_cli_selftest_and_mutation_check_exit_zero():
    assert main(["--selftest"]) == 0
    assert main(["--mutation-check"]) == 0


def test_void_cells_are_not_zeroes(tmp_path):
    """`infra_void` 的格不進配對，而且剔除率用**計畫題數**當分母。"""
    cells = apply_m1(fixture("rp_wins"))
    for c in cells:
        if c["task_id"] == "s1_00" and c["arm"] == "RS":
            c["void"], c["void_reason"] = True, "infra_void=rc=20"
    doc = analyse(cells)
    ps = doc["per_stratum"]["S1"]
    v = ps["void"]
    assert v["n_excluded"] == 1, "RS void ⇒ 該題三臂一起剔除"
    assert ps["h1"]["n_pairs"] == 49, "RS 壞掉的題，RF vs RP 也不准用（L-4）"
    assert ps["h2_control"]["n_pairs"] == 49, "H1 與 H2 要落在同一份題集上"
    assert ps["h1"]["three_arm_filter"] is True
    assert v["n_tasks_planned"] == 50
    # 負向控制：不套三臂過濾 ⇒ RF vs RP 會偷用那一題（50 對）
    assert bc_counts(cells, arm_a="RF", arm_b="RP", field="m1",
                     only_tasks=None)["n_pairs"] == 50


def test_alpha_and_thresholds_are_frozen():
    assert ALPHA == 0.05 and M7_FILE_BREACH == 0.10
    from ops.gain.r535.state_r535 import (
        CEILING_PASS_THRESHOLD, RULED_OUT_UPPER, TOST_DELTA,
        TRIGGER_FAIL_THRESHOLD, TRIGGER_N_EXPECTED, VOID_RATE_MAX)
    assert TRIGGER_FAIL_THRESHOLD == {"S1": 0.60, "S2": 0.30}
    assert TRIGGER_N_EXPECTED == {"S1": 150, "S2": 120}
    assert CEILING_PASS_THRESHOLD == 0.50
    assert VOID_RATE_MAX == 0.10
    assert TOST_DELTA == 0.15 and RULED_OUT_UPPER == 0.15


# ══ I-4：RS 不是單發臂（2026-09-19 修）══════════════════════════════════
def test_i4_does_not_flag_rs_for_retrying():
    """⚠ RS 是 `--retry resample --max-attempts 3`，**跑 3 次是正常的**。

    舊版的 I-4 把 RS 與 PC 一起要求 `attempts_used == 1`，理由寫著
    「它們是 `--retry none`」——那是本輪最早那次轉述錯誤（RS 被寫成
    `--retry none`）的殘留。預註冊已經更正，**收官器沒跟著改**。

    在 R535 的真資料上它誤報 69 格（S1）＋23 格（S2），**全部都是 RS**，
    而 PC 是 90/90 剛好 1 次。誤報不會改狀態（本檔只出聲），
    但它會讓讀報告的人以為資料有問題。
    """
    from ops.gain.r535 import state_r535 as S

    cells = [
        {"cell": "t1__RS", "stratum": "S1", "arm": "RS",
         "attempts_used": 3, "requests_seen": 9, "void": False},
        {"cell": "t1__RF", "stratum": "S1", "arm": "RF",
         "attempts_used": 3, "requests_seen": 9, "void": False},
        {"cell": "t1__PC", "stratum": "S1", "arm": "PC",
         "attempts_used": 1, "requests_seen": 3, "void": False},
    ]
    iv = S.invariants(cells, "S1")
    assert iv["i4_single_shot_arms_retried"]["n"] == 0, (
        f"RS 跑 3 次被當成違反了：{iv['i4_single_shot_arms_retried']['cells']}")


def test_i4_still_catches_pc_retrying():
    """PC 是唯一的單發臂 ⇒ 它 > 1 才是真違反（負控制）。"""
    from ops.gain.r535 import state_r535 as S

    cells = [
        {"cell": "t1__RS", "stratum": "S1", "arm": "RS",
         "attempts_used": 3, "requests_seen": 9, "void": False},
        {"cell": "t1__PC", "stratum": "S1", "arm": "PC",
         "attempts_used": 2, "requests_seen": 6, "void": False},
    ]
    iv = S.invariants(cells, "S1")
    assert iv["i4_single_shot_arms_retried"]["n"] == 1
    assert iv["i4_single_shot_arms_retried"]["cells"] == ["t1__PC"]
