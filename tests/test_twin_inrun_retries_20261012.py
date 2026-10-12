"""整合 e2e M7（2026-10-12）：嘗試進行中發給電視的卡，退回數要從事件流的 attempt_started 學，
否則被退回過的跑，電視少「被退回 N 次」那一句、和手機的最終卡對不上。"""
import json

from ops.exhibit.twin import fortune as fz
from ops.exhibit.twin import grounding_gate as gg


def _rd(tmp_path, n_attempts, run_json=None):
    ev = tmp_path / "events.jsonl"
    rows = [{"type": "run_started", "task_id": "t1", "arm": "RUN-ON", "run_id": "r1"}]
    rows += [{"type": "attempt_started", "run_id": "r1"} for _ in range(n_attempts)]
    ev.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    (tmp_path / gg.GATE_META_NAME).write_text(json.dumps({"events_path": str(ev), "task_id": "t1"}), encoding="utf-8")
    if run_json is not None:
        (tmp_path / "run_RUN-ON.json").write_text(json.dumps(run_json), encoding="utf-8")
    return tmp_path


def test_in_run_second_attempt_counts_one_retry(tmp_path):
    assert fz.attempts_retries(_rd(tmp_path, 2)) == 1          # run_RUN-ON.json 還沒寫：從事件流學


def test_first_attempt_no_retry(tmp_path):
    assert fz.attempts_retries(_rd(tmp_path, 1)) == 0


def test_final_run_json_still_counts(tmp_path):
    assert fz.attempts_retries(_rd(tmp_path, 3, {"attempts": [1, 2, 3]})) == 2


def test_nothing_readable_is_zero(tmp_path):
    assert fz.attempts_retries(tmp_path) == 0
