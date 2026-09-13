"""B 層六情境 harness 驗收（13 §3；17 §P4；vacant/blayer.py）。

鎖定每個情境的判準（事前寫死於 `_verdict`）——含 meta 判準：「拆掉機制，
數字必須變」（on/off 雙組是每個情境的內建反事實）。正式掃描是每格 ≥1000
seeds（`examples/b_layer.py`）；這裡用 8 seeds 的 smoke 格鎖行為不回退。
"""

from __future__ import annotations

import json
from collections import Counter

from vacant import blayer
from vacant.blayer import RATIOS, SCENARIOS, run_all


def _run(tmp_path, only=None):
    return run_all(n_seeds=8, base_seed="test-blayer", out_dir=tmp_path, only=only)


def test_all_six_scenarios_pass(tmp_path):
    reports = _run(tmp_path)
    assert set(reports) == set(SCENARIOS)
    for name, rep in reports.items():
        assert rep.verdict, f"{name} 未過判準：{rep.detail}"


def test_eight_ratios_and_both_arms(tmp_path):
    reports = _run(tmp_path, only=("decay_slash",))
    rep = reports["decay_slash"]
    assert len(rep.on_cells) == len(RATIOS) == 8
    assert len(rep.off_cells) == 8
    assert [c.ratio for c in rep.on_cells] == list(RATIOS)
    # 每格帶 bootstrap CI 且種子數正確
    for c in rep.on_cells:
        assert c.n_seeds == 8 and c.ci_lo <= c.value <= c.ci_hi


def test_mechanism_removed_numbers_must_change(tmp_path):
    """meta 判準（13 §3 核心）：每個情境拆掉機制，指標必須可觀測地變化——
    否則該機制是裝飾，要從一切主張移除。"""
    reports = _run(tmp_path)
    for name, rep in reports.items():
        on07 = next(c for c in rep.on_cells if abs(c.ratio - 0.7) < 1e-9).value
        off07 = next(c for c in rep.off_cells if abs(c.ratio - 0.7) < 1e-9).value
        assert on07 != off07, f"{name} 拆掉機制數字沒變（on={on07} off={off07}）→ 裝飾"


def test_output_artifacts_written(tmp_path):
    reports = _run(tmp_path)
    cells = (tmp_path / "cells.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(cells) == 6 * 8 * 2  # 六情境 × 8 格 × on/off
    first = json.loads(cells[0])
    for k in ("scenario", "ratio", "n_seeds", "value", "ci_lo", "ci_hi", "arm"):
        assert k in first
    summary = (tmp_path / "summary.md").read_text(encoding="utf-8")
    assert "B 層機制驗收六情境" in summary
    for name in reports:
        assert name in summary


def test_arm_label_is_not_value_equality(tmp_path):
    """`arm` 要真的分得出兩組——行數對、欄位在，都還不算數。

    上面那條只驗了「96 行」與「有 arm 這個 key」，**兩個都是前提**；
    實際寫出來的標籤對不對沒有人在問。原本的寫法是
    `"on" if c in rep.on_cells else "off"`，而 `Cell` 是 dataclass ⇒ `in` 走
    **值相等**：只要某格的 off 值與 on 值一樣，那個 off 就被寫成 "on"。
    1000 seeds 的正式掃描實測寫成 **on 58／off 38**、10 個重複鍵。

    ⚠ 會被標錯的正好是「**拆掉機制、數字沒變**」的格（ratio=0；
      same_source 的 ratio<0.5 依定義回 0）——而那是 13 §3 唯一用來判
      「該機制在該格是裝飾」的證據。標反的方向是**系統性偏向 on**。
    """
    _run(tmp_path)
    rows = [json.loads(l) for l in
            (tmp_path / "cells.jsonl").read_text(encoding="utf-8").splitlines()]
    arms = Counter(r["arm"] for r in rows)
    assert arms == {"on": 6 * 8, "off": 6 * 8}, f"arm 標籤不對稱：{dict(arms)}"
    keys = Counter((r["scenario"], r["arm"], r["ratio"]) for r in rows)
    dup = {k: v for k, v in keys.items() if v > 1}
    assert not dup, f"(scenario,arm,ratio) 重複鍵 {len(dup)} 個：{sorted(dup)[:5]}"


def test_ledger_is_written_while_running_not_after(tmp_path):
    """事件帳要是**邊跑邊寫**的：跑掛在半路，已經算完的格子必須還在。

    這條驗的是後果不是前提——「有 ledger_events.jsonl 這個檔」是前提，
    跑完由 reports 轉寫一份出來也能通過。真正的分界是崩潰時留下什麼：
    邊跑邊寫留下「跑到哪、算出什麼」，事後轉寫留下零。RECORD_SPEC §2 要的是
    生態事件流，而 CLAUDE.md 的紀錄紅線（不 pack＝沒跑過）要防的正是事後補帳。
    """
    calls = {"n": 0}

    def boom(ratio, rng, on):
        calls["n"] += 1
        if calls["n"] == 3:  # 第二格跑到一半
            raise RuntimeError("注入的崩潰")
        return 1.0

    orig = blayer.SCENARIOS
    # 放第一個 ⇒ 崩在整個掃描的最前面：事後轉寫在這裡會留下 0 筆
    blayer.SCENARIOS = {"crash_probe": (boom, "注入用"), **orig}
    # 不用 pytest.raises：這支刻意不 import pytest，執行端那台裝不了
    # （沒有 pip、裝要 sudo），而 B 層是那台在跑的——測試跑不了等於沒有測試。
    crashed = False
    try:
        run_all(n_seeds=2, base_seed="crash", out_dir=tmp_path)
    except RuntimeError:
        crashed = True
    finally:
        blayer.SCENARIOS = orig
    assert crashed, "注入的崩潰沒有發生 ⇒ 這條判準不成立"

    ledger = tmp_path / blayer.LEDGER_NAME
    assert ledger.exists(), "崩潰後事件帳整份不見 ⇒ 是跑完才寫的"
    rows = [json.loads(l) for l in
            ledger.read_text(encoding="utf-8").splitlines() if l.strip()]
    cells = [r for r in rows if r["type"] == "B_LAYER_CELL"]
    assert len(cells) >= 1, f"崩潰前算完的格子沒留下（事件 {len(rows)} 筆）"
    assert rows[0]["type"] == "B_LAYER_RUN_START"
    # 對照組：cells.jsonl 是跑完才寫的，所以這裡本來就該不存在
    assert not (tmp_path / "cells.jsonl").exists()


def test_ledger_and_cells_agree_cell_by_cell(tmp_path):
    """兩條**各自寫檔**的路徑（一條跑完寫、一條邊跑邊寫）對同一格說同一件事。

    漂移不需要有人犯錯就會發生——只要兩份程式各自被正確地修改了不同次數。
    第 36 輪的 arm 標錯就是這個形狀，而當時的測試只驗行數與欄位存在。
    """
    _run(tmp_path)
    cells = {(r["scenario"], r["arm"], r["ratio"]): r for r in
             (json.loads(l) for l in
              (tmp_path / "cells.jsonl").read_text(encoding="utf-8").splitlines())}
    led_rows = [json.loads(l) for l in
                (tmp_path / blayer.LEDGER_NAME).read_text(encoding="utf-8").splitlines()]
    led_cells = [r for r in led_rows if r["type"] == "B_LAYER_CELL"]
    led = {(r["scenario"], r["arm"], r["ratio"]): r for r in led_cells}

    assert len(led_cells) == len(led) == 6 * 8 * 2, "事件帳有重複鍵或漏格"
    assert Counter(k[1] for k in led) == {"on": 48, "off": 48}
    assert set(cells) == set(led)
    for k in cells:
        for f in ("n_seeds", "value", "ci_lo", "ci_hi"):
            assert cells[k][f] == led[k][f], f"{k} 的 {f} 兩份歸檔不一致"
    # 事件帳的頭尾與每情境判準都在
    assert led_rows[0]["type"] == "B_LAYER_RUN_START"
    assert led_rows[-1]["type"] == "B_LAYER_RUN_END" and led_rows[-1]["n_cells"] == 96
    assert {r["scenario"] for r in led_rows if r["type"] == "B_LAYER_VERDICT"} == set(SCENARIOS)


def test_pack_check_passes_and_absences_have_real_reasons(tmp_path):
    """紀錄紅線（CLAUDE.md）：不 pack ＝ 沒跑過。

    附帶驗「缺席理由是真的」：`record.pack` 對沒給的欄位會自動填「extra_meta
    未提供」——形式上通過、內容上說謊。blayer 沒有模型呼叫是**事實**，
    歸檔要寫的是那個事實。
    """
    from vacant.record import check

    reports = _run(tmp_path)
    ok, problems = blayer.finalize_run_package(
        tmp_path, reports, n_seeds=8, base_seed="test-blayer", elapsed_s=1.0)
    assert ok and not problems, problems
    assert check(tmp_path) == (True, [])

    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    for k in ("model_id", "endpoint", "wire.jsonl", "model_io.jsonl"):
        reason = manifest["missing"].get(k, "")
        assert reason and "extra_meta 未提供" not in reason, f"{k} 的缺席理由是佔位字串"
    # 沒有簽章鏈這件事要寫在歸檔裡，不是只寫在原始碼註解裡
    assert "SKIPPED" in (tmp_path / "chain_verify.txt").read_text(encoding="utf-8")
    for f in ("anomalies.md", "summary.md"):
        assert "誠實邊界" in (tmp_path / f).read_text(encoding="utf-8")


def test_deterministic_same_seed_same_result(tmp_path):
    a = run_all(n_seeds=4, base_seed="det", only=("same_source",))
    b = run_all(n_seeds=4, base_seed="det", only=("same_source",))
    va = [c.value for c in a["same_source"].on_cells]
    vb = [c.value for c in b["same_source"].on_cells]
    assert va == vb  # 同 seed 同結果（可重放／歸檔對帳前提）
