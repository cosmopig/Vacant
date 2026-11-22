"""ops/redo/analysis/p_model_calls.py：證據不足要說 UNKNOWN，不補零（2026-11-19 日報 P1 的負控制）。"""
from __future__ import annotations

import importlib.util
import json
import pathlib

import pytest

_spec = importlib.util.spec_from_file_location(
    "p_model_calls", pathlib.Path(__file__).resolve().parents[1] / "ops" / "redo" / "analysis" / "p_model_calls.py")
pmc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pmc)

CALL = json.dumps({"type": "message_end", "message": {"role": "assistant", "timestamp": 1}})
CALL2 = json.dumps({"type": "message_end", "message": {"role": "assistant", "timestamp": 2}})
TOOL = json.dumps({"type": "message_end", "message": {"role": "toolResult", "timestamp": 3}})


def _cell(root: pathlib.Path, name: str, attempts: list[tuple[float, str | None]]) -> pathlib.Path:
    """attempts：每一次嘗試 (wall_s, 日誌內容或 None＝沒有日誌檔)。"""
    cell = root / "cells" / name / "r1" / "P"
    run = cell / "attempt_1" / "logs" / "vacant-work" / "restart-x"
    run.mkdir(parents=True)
    (cell / "cell.json").write_text("{}")
    (run / "result.json").write_text(json.dumps(
        {"attempts": [{"attempt": i + 1, "wall_s": w} for i, (w, _) in enumerate(attempts)]}))
    for i, (_, text) in enumerate(attempts):
        d = run / f"attempt_{i + 1}" / "logs"
        d.mkdir(parents=True)
        if text is not None:
            (d / "agent_stdout.log").write_text(text)
    return cell


def test_complete_cell_counts_assistant_calls_across_attempts(tmp_path):
    c = _cell(tmp_path, "t", [(100, f"{CALL}\n{TOOL}\n{CALL2}\n"), (50, f"{CALL}\n")])
    r = pmc.cell_calls(str(c))
    assert r == {"status": "known", "calls": 3, "attempts": 2, "why": None}


def test_missing_log_is_unknown_not_zero(tmp_path):
    c = _cell(tmp_path, "t", [(100, f"{CALL}\n"), (100, None)])
    r = pmc.cell_calls(str(c))
    assert r["status"] == "unknown" and r["calls"] is None and "沒有日誌" in r["why"]


def test_empty_log_after_long_attempt_is_unknown(tmp_path):
    c = _cell(tmp_path, "t", [(300, "")])
    assert pmc.cell_calls(str(c))["status"] == "unknown"


def test_empty_log_after_instant_failure_counts_as_zero(tmp_path):
    c = _cell(tmp_path, "t", [(2, "")])          # 秒退（例如啟動失敗）：0 次是真的
    assert pmc.cell_calls(str(c)) == {"status": "known", "calls": 0, "attempts": 1, "why": None}


def test_truncated_json_line_is_unknown(tmp_path):
    c = _cell(tmp_path, "t", [(100, f"{CALL}\n{CALL2[:20]}\n")])
    r = pmc.cell_calls(str(c))
    assert r["status"] == "unknown" and "無法解析" in r["why"]


def test_duplicate_lines_count_once(tmp_path):
    c = _cell(tmp_path, "t", [(100, f"{CALL}\n{CALL}\n{CALL2}\n")])
    assert pmc.cell_calls(str(c))["calls"] == 2


def test_missing_result_json_is_unknown(tmp_path):
    cell = tmp_path / "cells" / "t" / "r1" / "P"
    cell.mkdir(parents=True)
    (cell / "cell.json").write_text("{}")
    assert pmc.cell_calls(str(cell))["status"] == "unknown"


def test_summary_averages_only_known_cells_and_lists_unknown(tmp_path):
    _cell(tmp_path, "a", [(100, f"{CALL}\n{CALL2}\n")])
    _cell(tmp_path, "b", [(100, f"{CALL}\n{CALL}\n{CALL2}\n{TOOL}\n"), (100, f"{CALL}\n{CALL2}\n")])
    _cell(tmp_path, "c", [(100, None)])
    s = pmc.summarize(str(tmp_path))
    assert s["cells"] == 3 and s["known"] == 2 and s["unknown"] == 1
    assert s["mean_calls"] == 3.0                # (2 + 4) / 2；缺日誌那格不算成 0
    assert list(s["unknown_cells"]) == ["c/r1/P"]


def _cell_raw(root: pathlib.Path, name: str, result: dict) -> pathlib.Path:
    cell = root / "cells" / name / "r1" / "P"
    run = cell / "attempt_1" / "logs" / "vacant-work" / "restart-x"
    run.mkdir(parents=True)
    (cell / "cell.json").write_text("{}")
    (run / "result.json").write_text(json.dumps(result))
    return cell


def test_missing_attempts_field_is_unknown_not_zero(tmp_path):
    """2026-11-22 日報 P1 負控制：result.json 沒有 attempts 欄位 ⇒ UNKNOWN，不是 known／0 次呼叫。"""
    r = pmc.cell_calls(str(_cell_raw(tmp_path, "t", {"accepted": False})))
    assert r["status"] == "unknown" and r["calls"] is None and "沒有 attempts" in r["why"]


def test_empty_attempts_list_is_unknown_not_zero(tmp_path):
    r = pmc.cell_calls(str(_cell_raw(tmp_path, "t", {"attempts": [], "baseline_error": "x"})))
    assert r["status"] == "unknown" and r["calls"] is None and "空陣列" in r["why"] and "baseline_error" in r["why"]


def test_summary_does_not_average_in_empty_attempt_cells(tmp_path):
    _cell(tmp_path, "good", [(10.0, CALL + "\n" + CALL2 + "\n")])
    _cell_raw(tmp_path, "empty", {"attempts": []})
    s = pmc.summarize(str(tmp_path))
    assert s["known"] == 1 and s["unknown"] == 1 and s["mean_calls"] == 2


@pytest.mark.parametrize("entry", [{"attempt": 1}, {"attempt": 1, "wall_s": None},
                                   {"attempt": 1, "wall_s": "abc"}, "x", 3])
def test_corrupt_attempt_is_unknown(tmp_path, entry):
    c = _cell(tmp_path, "t", [(2, "")])
    result = next(c.glob("attempt_*/logs/vacant-work/restart-*/result.json"))
    result.write_text(json.dumps({"attempts": [entry]}))
    r = pmc.cell_calls(str(c))
    assert r["status"] == "unknown" and r["calls"] is None and r["why"]


@pytest.mark.parametrize("line", ["[]", '"x"', "3", "null",
                                  '{"type":"message_end","message":3}'])
def test_non_object_log_is_unknown(tmp_path, line):
    c = _cell(tmp_path, "t", [(2, line + "\n")])
    r = pmc.cell_calls(str(c))
    assert r["status"] == "unknown" and r["calls"] is None and "無法解析" in r["why"]


def test_missing_attempt_identifier_is_explicitly_unknown(tmp_path):
    c = _cell_raw(tmp_path, "t", {"attempts": [{"wall_s": 2}]})
    r = pmc.cell_calls(str(c))
    assert r["status"] == "unknown" and r["calls"] is None and "attempt 欄位" in r["why"]


def test_summary_survives_corrupt_cell(tmp_path):
    _cell(tmp_path, "good", [(2, CALL)])
    _cell_raw(tmp_path, "corrupt", {"attempts": [3]})
    s = pmc.summarize(str(tmp_path))
    assert s["known"] == 1 and s["unknown"] == 1 and s["mean_calls"] == 1


def test_empty_log_at_duration_boundary_is_known(tmp_path):
    c = _cell(tmp_path, "t", [(pmc.MIN_WALL_S, "")])
    assert pmc.cell_calls(str(c))["calls"] == 0
