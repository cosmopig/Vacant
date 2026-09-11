"""`ops/gain/analyze_r529.py` 的紅線（R529 收官分析尺）。

這支在架構裡承重什麼：analyzer 改壞了**不會噴錯**，它會照樣吐出一份看起來很合理的
JSON，然後被讀成裁決。所以每一種壞法都要有一條紅線，而且要**跑得到**：

  1. `--selftest` 的 11 組手算對照全過；
  2. `--mutation-check` 的 5 種突變**全部**要被抓到
     （抓不到的突變＝那條紅線其實不存在）；
  3. 沒有資料時不准當掉、不准假裝有結論（四集 INVALID ⇒ state=INVALID）；
  4. 預註冊指名的仲裁欄位**每一個都要存在**——判準指名了一個不存在的 key，
     `.get()` 會安靜地回 None，然後被讀成「量到 0」。
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ops.gain.analyze_r529 import (  # noqa: E402
    ARMS, FAMILY_SIZE, PAIRS, SETS, SET_N, analyze, decide, included_sets,
    mutation_check, paired, primary, refutation, selftest, tokens_by_arm,
)

DECISION = ROOT / "DECISION_20260911_R529_CROSS_BANK_PREREG.md"


def test_selftest_passes():
    assert selftest() == 0


def test_every_mutation_is_caught():
    """抓不到的突變＝那條紅線其實不存在，而它會安靜地改掉裁決。"""
    assert mutation_check() == 0


def test_shape_matches_the_prereg():
    assert list(ARMS) == ["OFF", "CONFORM", "HMIX"]
    assert PAIRS == (("HMIX", "CONFORM"), ("HMIX", "OFF"))
    assert FAMILY_SIZE == 2
    assert SET_N == {"lcb3_medium": 135, "lcb3_hard": 54,
                     "humanevalplus": 156, "evalplus": 371}
    assert sum(SET_N.values()) == 716
    assert sum(len(v) for v in SETS.values()) == 37


def test_every_block_name_is_registered_in_the_decision():
    """analyzer 讀的塊名必須就是預註冊授權的那 37 個。"""
    text = DECISION.read_text(encoding="utf-8")
    for blocks in SETS.values():
        for b in blocks:
            assert f"R529_BLOCK: {b} " in text, b


def test_no_data_yields_invalid_not_a_verdict(tmp_path):
    """量不到不是通過：四集都沒有資料 ⇒ INVALID，而且不准當掉。"""
    a = analyze(tmp_path)
    assert a["sets_included_in_primary"] == []
    assert a["decision_state"]["state"] == "INVALID"
    for s in SETS:
        assert a["per_set"][s]["valid"] is False
        assert a["per_set"][s]["broken_reasons"]


def test_arbiter_keys_named_by_the_prereg_all_exist():
    """§六 指名的每一個仲裁欄位都要在輸出裡（用合成資料走完整條路）。"""
    prim = primary(
        {s: {"paired": {f"{a}_vs_{b}": {"b": 6, "c": 1, "n_common": 20,
                                        "p_mcnemar_exact": 0.125}
                        for a, b in PAIRS}} for s in SETS},
        list(SETS))
    assert prim["family_size"] == 2
    for a, b in PAIRS:
        k = f"{a}_vs_{b}"
        for key in ("b", "c", "n_discordant", "p", "p_adj", "significant",
                    "per_stratum", "heterogeneity", "pooling_identity_note"):
            assert key in prim[k], (k, key)
        assert len(prim[k]["per_stratum"]) == 4
        # 分層 ≡ 合併（POOLING_IDENTITY_NOTE 那句話要是真的）
        assert prim[k]["p"] == prim[k]["pooling_identity_check"]
    d = decide(prim, {"HMIX": {"tpc_incl_void": 1.0},
                      "CONFORM": {"tpc_incl_void": 2.0}})
    for key in ("state", "cond_i_both_primary_holm",
                "cond_ii_tpc_hmix_le_conform", "note"):
        assert key in d
    assert "R460" in d["note"]          # 不可與 R460 的同名狀態互引


def test_family_size_survives_a_dropped_set():
    """少一集只把它從 N 裡拿掉，**家族仍然是 2**（§六-2 的禁令）。"""
    ps = {s: {"paired": {f"{a}_vs_{b}": {"b": 4, "c": 1, "n_common": 20,
                                         "p_mcnemar_exact": 0.375}
                         for a, b in PAIRS}} for s in SETS}
    p = primary(ps, ["lcb3_medium", "humanevalplus"])
    assert p["family_size"] == 2
    assert p["HMIX_vs_CONFORM"]["k_strata"] == 2
    assert p["excluded_sets"] == ["lcb3_hard", "evalplus"]
    assert "N 少了" in p["exclusion_note"]


def test_refutation_key_is_only_lcb3():
    """R460 §九 第一條寫的是 LCB v3；MBPP+／HumanEval+ 不是觸發鍵但要照實報。"""
    ps = {"lcb3_hard": {"paired": {"HMIX_vs_CONFORM": {"b": 9, "c": 1}}},
          "lcb3_medium": {"paired": {"HMIX_vs_CONFORM": {"b": 9, "c": 1}}},
          "evalplus": {"paired": {"HMIX_vs_CONFORM": {"b": 1, "c": 9}}}}
    r = refutation(ps)
    assert r["triggered"] is False            # lcb3 兩層都 b > c
    assert r["evalplus_c_ge_b"] is True       # 但 evalplus 反向要報出來
    assert set(r["keys"]) == {"lcb3_hard", "lcb3_medium"}


def test_cli_runs_and_writes_json(tmp_path):
    out = tmp_path / "a.json"
    r = subprocess.run(
        [sys.executable, str(ROOT / "ops" / "gain" / "analyze_r529.py"),
         "--root", str(tmp_path), "--json", str(out)],
        capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stderr[-800:]
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["run"] == "R529"
    assert data["decision"] == DECISION.name


def test_deliv_and_denominator_are_the_frozen_definitions():
    rows_a = [{"arm": "HMIX", "task_id": "t1", "accepted": True,
               "meets_demand": True, "calls_used": 1}]
    rows_b = [{"arm": "OFF", "task_id": "t1", "accepted": True,
               "meets_demand": False, "calls_used": 1},
              {"arm": "OFF", "task_id": "t2", "accepted": True,
               "meets_demand": True, "calls_used": 1}]
    pr = paired(rows_a, rows_b)
    assert pr["n_common"] == 1 and (pr["b"], pr["c"]) == (1, 0)
    tb = tokens_by_arm(
        [{"ok": True, "usage": {"total_tokens": 5},
          "meta": {"arm": "HMIX", "task_id": "zz"}}], {"HMIX": set()})["HMIX"]
    assert tb["tokens_incl_void"] == 5 and tb["tokens_excl_void"] == 0


def test_included_sets_only_drops_invalid():
    assert included_sets({s: {"valid": True} for s in SETS}) == list(SETS)
