"""D1 離線 claim 重播的 pytest（零模型）。

跑法：python3 -m pytest tests/test_replay_claims.py -v
"""
import importlib.util
import json
import pathlib
import tempfile
from unittest.mock import patch

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("replay_claims", REPO / "ops/reqloop/extract/replay_claims.py")
rc = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(rc)

UT, INPUTS = rc.load_task("g3_2", "dab_725")
KEYS = [{"key": "mean1", "type": "number"}]


def test_selftest_all_controls_pass():
    assert rc.selftest() == 0


def test_negative_controls_non_deterministic():
    # deliverable = 輸入 CSV 路徑
    ok, reason = rc.judge_claim("answer_kv", "data/auto-mpg.csv", {"keys": KEYS}, UT, INPUTS)
    assert not ok and reason == "deliverable_is_input_file"
    # deliverable = 不存在的檔名
    ok, reason = rc.judge_claim("answer_kv", "no_such_output_9x7z.csv", {"keys": KEYS}, UT, INPUTS)
    assert not ok and reason.startswith("deliverable_not_in_request")
    # verifier 不在白名單
    ok, reason = rc.judge_claim("totally_bogus_verifier", "answer.txt", {}, UT, INPUTS)
    assert not ok and reason == "unknown_verifier:totally_bogus_verifier"


def test_positive_control_deterministic():
    ok, reason = rc.judge_claim("answer_kv", "answer.txt", {"keys": KEYS}, UT, INPUTS)
    assert ok and reason is None


def test_replay_reason_behavior():
    # D3: mean_col 已為 deterministic
    assert rc.replay_reason("unsupported_recompute_type:mean_col", UT, INPUTS, "plain_recomputed") == (True, None)
    # D3b: pearson 已為 deterministic
    assert rc.replay_reason("unsupported_recompute_type:pearson", UT, INPUTS, "plain_recomputed") == (True, None)
    # 未支援的虛構型別 → 非 deterministic
    assert rc.replay_reason("unsupported_recompute_type:bogus_stat_9x", UT, INPUTS, "plain_recomputed") == (
        False, "unsupported_recompute_type:bogus_stat_9x")
    # 已在支援集合的型別 → 翻 deterministic（D3 擴充後的行為形狀）
    assert rc.replay_reason("unsupported_recompute_type:zcount3", UT, INPUTS, "kv_recomputed") == (True, None)
    # missing_param → missing_raw，不造假（P20261113_1708-2：點名保留根因碼）
    assert rc.replay_reason("missing_param:values", UT, INPUTS) == (None, "missing_param:values")
    # model_declared_unverified → fail-closed
    assert rc.replay_reason("model_declared_unverified", UT, INPUTS)[0] is False


def test_baseline_totals():
    rows = rc.collect()
    s = rc.summarize(rows)
    assert s["total"] == 76
    assert s["missing_raw"] == 3  # 2 deterministic + 1 missing_param:values
    assert s["replayable"] == 73
    assert s["deterministic"] == 14  # D3 (12) + D3b (2) 全部 14 條 unsupported 皆已落地
    assert s["baseline"]["baseline_match"] is True
    assert s["baseline"]["deterministic_in_missing_raw"] == 2
    # 每行都有必要欄位
    for r in rows:
        assert r["replay_status"] in ("unverified", "deterministic", "missing_raw")
        assert r["task_id"] and r["claim_id"] and r["source"]


def test_reason_distribution_and_unsupported_types():
    s = rc.summarize(rc.collect())
    assert s["reason_distribution"]["deliverable_not_in_request:*"] == 52
    assert s["reason_distribution"]["deterministic"] == 14
    assert s["unsupported_recompute_types"] == {"mean_col": 8, "median_col": 2, "pearson": 2, "std_col": 2}


def test_gate_check_passes():
    """成效門機械檢驗綠燈：deterministic >= 30 且負控制 0 假 PASS。"""
    assert rc.gate_check() == 0


def test_gate_check_negative_control_fails_on_false_pass():
    """負控制：若有假 PASS，gate_check 必須失敗退出（exit 1）。"""
    with patch.object(rc, "judge_claim", return_value=(True, None)):
        assert rc.gate_check() == 1


def test_replay_claims_gate_flag(capsys):
    """P20261113_0846-3：--gate 命令列路徑執行成功，輸出含 GATE_CHECK: 與 VERDICT: PASS。"""
    assert rc.main(["--gate"]) == 0
    out = capsys.readouterr().out
    assert "GATE_CHECK:" in out and "VERDICT: PASS" in out
    assert rc.run_gate_check is rc.gate_check  # 票面函式名為同一實作


def test_replay_claims_verify_specs_flag(capsys):
    """P20261113_1206-3：--verify-specs 交叉驗證 4 題 G4 凍結規格（正控制必 PASS、負控制必非 PASS、0 假 PASS）。"""
    assert rc.main(["--verify-specs"]) == 0
    out = capsys.readouterr().out
    assert "FROZEN_SPECS:" in out and "VERDICT: PASS" in out


def test_replay_claims_verify_specs_flag_neg_control(tmp_path, capsys):
    """P20261113_1206-3 負控制：規格自 hash 被篡改 → verify_frozen_specs 必 FAIL（RC 1）。"""
    import copy
    src = REPO / "ops/reqloop/g4/specs/dab_725.json"
    raw = json.loads(src.read_text(encoding="utf-8"))
    raw = copy.deepcopy(raw)
    raw["items"][0]["quote"] = "TAMPERED"
    (tmp_path / "dab_725.json").write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    for tid in ("dab_587", "dab_657", "dab_517"):
        (tmp_path / f"{tid}.json").write_bytes((REPO / "ops/reqloop/g4/specs" / f"{tid}.json").read_bytes())
    assert rc.verify_frozen_specs(tmp_path) == 1
    assert "FROZEN_SPECS FAIL" in capsys.readouterr().out


def test_replay_claims_json_flag(capsys):
    """P20261113_0948-3：--json 輸出機器可讀統計（K1 trusted）。

    驗證：RC 0、stdout 可被 json.loads 解析、"deterministic" 為整數（現值 66＝成效門口徑）、
    內含 "by_task"（每題 total/deterministic/unverified/missing_raw，分組合計＝76）。
    """
    assert rc.main(["--json"]) == 0
    doc = json.loads(capsys.readouterr().out)
    assert isinstance(doc["deterministic"], int)
    assert doc["deterministic"] == 66
    assert doc["totals"]["deterministic"] == 66
    by = doc["by_task"]
    assert isinstance(by, dict) and by
    assert sum(t["total"] for t in by.values()) == 76
    for t in by.values():
        assert t["total"] == t["deterministic"] + t["unverified"] + t["missing_raw"]


# ── P20261113_1358-2：--missing-report 點名缺失欄位 ──────────────────────────

def test_missing_field_reason_point_names_only():
    """缺失欄位點名：只回欄位名＋原因碼，永不回欄位值。

    - original_reason=missing_param:<field> → field=<field>、reason=missing_param
      （欄位名取自 reason 碼本身；reason 是機器碼，不是值）。
    - 原始 deterministic（來源只存 claim id、raw 欄位未存）→ field=verifier
      （judge 契約首個未存欄位）、reason=raw_fields_not_saved。
    """
    assert rc.missing_field_reason({"original_reason": "missing_param:values"}) == ("values", "missing_param")
    assert rc.missing_field_reason({"original_reason": "missing_param:col_name"}) == ("col_name", "missing_param")
    assert rc.missing_field_reason({"original_reason": None}) == ("verifier", "raw_fields_not_saved")
    assert rc.missing_field_reason({}) == ("verifier", "raw_fields_not_saved")


def test_missing_report_flag_lists_each_missing_claim_at_tail(capsys):
    """--missing-report：RC 0、點名列出全部 3 條缺失、CLAIM_MISSING 行在 stdout 末尾。"""
    assert rc.main(["--missing-report"]) == 0
    out = capsys.readouterr().out
    lines = [l for l in out.splitlines() if l.strip()]
    tail = [l for l in lines if l.startswith("CLAIM_MISSING: ")]
    assert len(tail) == 3
    # 末尾 3 行即 3 條點名（排序穩定、無值外洩的格式）
    assert lines[-3:] == sorted([
        "CLAIM_MISSING: dab_517/req_data_unchanged: values missing_param",
        "CLAIM_MISSING: dab_725/R1: verifier raw_fields_not_saved",
        "CLAIM_MISSING: dab_725/R6: verifier raw_fields_not_saved",
    ])


def test_missing_report_lines_are_point_named_no_values(capsys):
    """負控制（票：點名欄位名、不印欄位值）：每行必須恰為
    CLAIM_MISSING: <task>/<claim>: <field> <reason>——多一個 token（即值）即紅。"""
    import re
    assert rc.main(["--missing-report"]) == 0
    out = capsys.readouterr().out
    lines = [l for l in out.splitlines() if l.startswith("CLAIM_MISSING: ")]
    assert len(lines) == 3
    for l in lines:
        assert re.fullmatch(r"CLAIM_MISSING: \S+/\S+: \S+ \S+", l), (
            f"行非點名格式（疑印了欄位值）: {l!r}")


def test_json_totals_missing_detail_shape(capsys):
    """--json totals 內含 missing_detail：3 條、每條恰 {task_id, claim_id, field, reason}；
    K1 deterministic 計數不受影響（仍 66）；K0 亦不受影響（summarize K0 同結構）。"""
    assert rc.main(["--json"]) == 0
    doc = json.loads(capsys.readouterr().out)
    md = doc["totals"]["missing_detail"]
    assert isinstance(md, list) and len(md) == 3
    for e in md:
        assert set(e) == {"task_id", "claim_id", "field", "reason"}
    assert {"task_id": "dab_517", "claim_id": "req_data_unchanged", "field": "values",
            "reason": "missing_param"} in md
    assert {"task_id": "dab_725", "claim_id": "R1", "field": "verifier",
            "reason": "raw_fields_not_saved"} in md
    assert {"task_id": "dab_725", "claim_id": "R6", "field": "verifier",
            "reason": "raw_fields_not_saved"} in md
    # K0/K1 計數不變（票紅線：不改變 K0/K1 確定性計數）
    assert doc["totals"]["deterministic"] == 66
    s0 = rc.summarize(rc.collect())
    assert s0["deterministic"] == 14
    assert s0["missing_raw"] == 3
    assert s0["missing_detail"] == doc["totals"]["missing_detail"]


# ── P20261113_1507-1：dab_587 unknown_verifier:missing 根因點名＋負控制 ──────

def test_missing_verifier_stays_unverified_negative_control():
    """P20261113_1507-1：verifier 缺失（空字串/None）必判 unknown_verifier:missing，
    絕不翻 deterministic（I-4：未測量不是通過；0 假 PASS 負控制）。

    dab_587 三條根因＝模型擷取階段省略 verifier 欄位且預跑未存 raw fields：
    (a) judge_claim 空/None → (False, "unknown_verifier:missing")（對齊 extract.py:806）；
    (b) replay_reason("unknown_verifier:missing") 維持 (False, reason)；
    (c) dab_587 的 3 條重播 row 維持 unverified 且 replay_reason 點名此根因。
    """
    # (a) judge_claim：空字串與 None 皆點名為 missing（對齊 extract.py:806 的 or 'missing'）
    assert rc.judge_claim("", "answer.txt", {}, UT, INPUTS) == (False, "unknown_verifier:missing")
    assert rc.judge_claim(None, "answer.txt", {}, UT, INPUTS) == (False, "unknown_verifier:missing")
    # (b) replay_reason：unknown_verifier:missing 維持 unverified（0 假 PASS 負控制）
    assert rc.replay_reason("unknown_verifier:missing", UT, INPUTS) == (False, "unknown_verifier:missing")
    # (c) dab_587 三條（模型省略 verifier、預跑未存 raw fields）維持 unverified 且點名根因
    rows = [r for r in rc.collect(use_trusted=True)
            if r["task_id"] == "dab_587" and r["replay_status"] == "unverified"]
    assert len(rows) == 3
    assert all(r["replay_reason"] == "unknown_verifier:missing" for r in rows)
    assert all(r["claim_id"] in ("req-3", "req-4", "req-5") for r in rows)


# ── P20261113_1708-2：dab_517 missing_param:values 根因點名＋負控制 ────────────

def test_missing_param_values_stays_missing_raw_negative_control():
    """P20261113_1708-2：缺必要參數（dab_517 req_data_unchanged missing_param:values）
    絕不判 deterministic（I-4：未測量不是通過；0 假 PASS 負控制）。

    (a) replay_reason 明確回 (None, "missing_param:values")：missing_raw、但保留缺失原因碼（不抹除根因）；
    (b) collect(use_trusted=True) 重播 row：replay_status == "missing_raw" 且
        replay_reason == "missing_param:values"（絕不翻 deterministic）。
    """
    # (a) replay_reason 點名：missing_raw 但保留根因碼（而非 (None, None) 抹除）
    assert rc.replay_reason("missing_param:values", UT, INPUTS) == (None, "missing_param:values")
    # (b) dab_517/req_data_unchanged 維持 missing_raw（0 假 PASS 負控制）
    rows = [r for r in rc.collect(use_trusted=True)
            if r["task_id"] == "dab_517" and r["claim_id"] == "req_data_unchanged"]
    assert len(rows) == 1
    assert rows[0]["replay_status"] == "missing_raw"
    assert rows[0]["replay_reason"] == "missing_param:values"
    assert rows[0]["replay_status"] != "deterministic"


# ── P20261113_1810-4：manifest 雜湊綁定核驗＋負控制 ────────────────────────

def test_replay_claims_verify_specs_tampered_manifest_fails_closed(tmp_path, capsys):
    """P20261113_1810-4：manifest spec_sha256 被篡改 → verify_frozen_specs 必 fail-closed
    （RC 1、輸出點名「FROZEN_SPECS FAIL: manifest integrity」）；0 假 PASS。"""
    m = json.loads((REPO / "ops/reqloop/g4/manifest.json").read_text(encoding="utf-8"))
    m["specs"]["dab_725"]["spec_sha256"] = "0" * 64
    mp = tmp_path / "manifest_tampered.json"
    mp.write_text(json.dumps(m, ensure_ascii=False), encoding="utf-8")
    assert rc.verify_frozen_specs(manifest_path=mp) == 1
    assert "FROZEN_SPECS FAIL: manifest integrity" in capsys.readouterr().out


# ── P20261113_1900-1：--unverified-report 點名全部非確定性 claim ─────────────

EXPECTED_UNVERIFIED = sorted([
    "CLAIM_UNVERIFIED: dab_725/R4: model_declared_unverified",
    "CLAIM_UNVERIFIED: dab_725/R7: model_declared_unverified",
    "CLAIM_UNVERIFIED: dab_587/req-3: unknown_verifier:missing",
    "CLAIM_UNVERIFIED: dab_587/req-4: unknown_verifier:missing",
    "CLAIM_UNVERIFIED: dab_587/req-5: unknown_verifier:missing",
    "CLAIM_UNVERIFIED: dab_517/req_write_answer_txt: model_declared_unverified",
    "CLAIM_UNVERIFIED: dab_517/req_do_not_modify_data: model_declared_unverified",
])


def test_unverified_report_flag_names_all_seven_claims(capsys):
    """P20261113_1900-1 (a)：--unverified-report RC0、恰 7 條點名（只印原因碼、不印欄位值）；
    0 條把錯判 PASS（無任何一行含 PASS／deterministic 語意翻轉）。"""
    assert rc.main(["--unverified-report"]) == 0
    out = capsys.readouterr().out
    lines = [l for l in out.splitlines() if l.startswith("CLAIM_UNVERIFIED: ")]
    assert lines == EXPECTED_UNVERIFIED  # 恰 7 條、逐條點名（多一條/少一條/換序皆紅）
    for l in lines:
        assert "PASS" not in l, f"unverified 條不得含 PASS 語意：{l!r}"
        assert "deterministic" not in l, f"unverified 條不得翻成 deterministic：{l!r}"
        assert l.split(": ", 2)[2] in ("model_declared_unverified", "unknown_verifier:missing")


def test_unverified_report_missing_report_output_unchanged(capsys):
    """P20261113_1900-1 (b) 負控制：--missing-report 既有 3 條輸出逐字不變（舊行為未被改到）。"""
    assert rc.main(["--missing-report"]) == 0
    lines = [l for l in capsys.readouterr().out.splitlines() if l.strip()]
    assert lines == [
        "REPLAY K1 (trusted): total=76 deterministic=66 unverified=7 missing_raw=3",
        "CLAIM_MISSING: dab_517/req_data_unchanged: values missing_param",
        "CLAIM_MISSING: dab_725/R1: verifier raw_fields_not_saved",
        "CLAIM_MISSING: dab_725/R6: verifier raw_fields_not_saved",
    ]


def test_unverified_report_gate_still_passes(capsys):
    """P20261113_1900-1 (c)：--gate 仍 deterministic=66/76 >= 30 false_pass=0 VERDICT: PASS。"""
    assert rc.main(["--gate"]) == 0
    assert ("GATE_CHECK: deterministic=66/76 >= 30 false_pass=0 VERDICT: PASS"
            in capsys.readouterr().out)


def test_unverified_report_json_named_non_deterministic(capsys):
    """P20261113_1900-1 步驟2：--json 既有欄位不變，totals 旁純加法新增
    named_non_deterministic（7 條 task/claim/reason 逐條清單）。"""
    assert rc.main(["--json"]) == 0
    doc = json.loads(capsys.readouterr().out)
    nn = doc["named_non_deterministic"]
    assert isinstance(nn, list) and len(nn) == 7
    for e in nn:
        assert set(e) == {"task_id", "claim_id", "reason"}
    assert {"task_id": "dab_587", "claim_id": "req-3", "reason": "unknown_verifier:missing"} in nn
    assert {"task_id": "dab_725", "claim_id": "R4", "reason": "model_declared_unverified"} in nn
    assert {"task_id": "dab_517", "claim_id": "req_do_not_modify_data",
            "reason": "model_declared_unverified"} in nn
    # 既有欄位不變（負控制：下游不破）
    assert doc["totals"]["deterministic"] == 66
    assert doc["totals"]["unverified"] == 7
    assert doc["totals"]["missing_raw"] == 3
    assert doc["totals"]["reason_distribution"]["model_declared_unverified"] == 4
    assert doc["totals"]["reason_distribution"]["unknown_verifier:missing"] == 3
    assert doc["deterministic"] == 66
