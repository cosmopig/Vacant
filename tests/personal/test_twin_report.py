"""跨模型報告。目錄裡的數字是合成的，不是試驗結果。"""

from __future__ import annotations

import json
from pathlib import Path

from vacant_network.personal.cli import main
from vacant_network.personal.twin_report import decide_one, load_run, render_report


def _scores(*, structured: float, summary: float, majority: float, raw: float, demo: float, none: float, diff: float, boot: list[float], ceiling: float) -> dict:
    def arm(value: float) -> dict:
        return {
            "micro_accuracy": value,
            "strict_accuracy": value,
            "micro_wilson95": [max(0.0, value - 0.1), min(1.0, value + 0.1)],
            "option_order": {"identity": {"n": 4, "accuracy": value}, "swapped": {"n": 4, "accuracy": value}},
        }
    return {
        "arms": {
            "MAJORITY": arm(majority),
            "DEMOGRAPHICS": arm(demo),
            "NONE": arm(none),
            "RAW": arm(raw),
            "SUMMARY": arm(summary),
            "STRUCTURED": arm(structured),
        },
        "pairs": [{
            "left": "SUMMARY",
            "right": "STRUCTURED",
            "n": 8,
            "mcnemar_b_right_only": 3,
            "mcnemar_c_left_only": 1,
            "mcnemar_p": 0.5,
            "accuracy_diff_right_minus_left": diff,
            "bootstrap95": boot,
        }, {
            "left": "NONE",
            "right": "STRUCTURED",
            "n": 8,
            "mcnemar_b_right_only": 2,
            "mcnemar_c_left_only": 2,
            "mcnemar_p": 1.0,
            "accuracy_diff_right_minus_left": structured - none,
            "bootstrap95": [-0.1, 0.1],
        }, {
            "left": "NONE",
            "right": "SUMMARY",
            "n": 8,
            "mcnemar_b_right_only": 1,
            "mcnemar_c_left_only": 1,
            "mcnemar_p": 1.0,
            "accuracy_diff_right_minus_left": summary - none,
            "bootstrap95": [-0.1, 0.1],
        }, {
            "left": "NONE",
            "right": "RAW",
            "n": 8,
            "mcnemar_b_right_only": 1,
            "mcnemar_c_left_only": 1,
            "mcnemar_p": 1.0,
            "accuracy_diff_right_minus_left": raw - none,
            "bootstrap95": [-0.1, 0.1],
        }],
        "retests": {"p": {"rate": ceiling, "compared": 4, "agreed": int(round(ceiling * 4))}},
        "preliminary_reference": {"test_retest_ceiling": 0.83, "majority_floor": 0.56, "n_people": 294},
    }


def _predictions(unsure_arm: str | None = None) -> list[dict]:
    rows = []
    for arm in ("MAJORITY", "DEMOGRAPHICS", "NONE", "RAW", "SUMMARY", "STRUCTURED"):
        for case_id in ("W4:Q1", "W4:Q2"):
            prediction = "unsure" if arm == unsure_arm and case_id == "W4:Q1" else "A"
            rows.append({
                "pid": "p", "arm": arm, "case_id": case_id, "status": "completed",
                "prediction": prediction, "presented_order": ["option_1", "option_2"],
            })
    return rows


def _write(directory: Path, model_id: str, scores: dict, predictions: list[dict], *, wall: int) -> None:
    directory.mkdir(parents=True)
    (directory / "run_meta.json").write_text(json.dumps({"model_id": model_id, "seed": 1, "participants": 1}) + "\n")
    (directory / "scores.json").write_text(json.dumps(scores) + "\n")
    (directory / "predictions.jsonl").write_text("".join(json.dumps(row) + "\n" for row in predictions))
    (directory / "calls.jsonl").write_text(json.dumps({
        "sent": True, "status": "completed", "cost_usd": 0.0, "usage": {"prompt_tokens": 3, "completion_tokens": 2},
        "wall_ms": wall, "budget_request": True,
    }) + "\n" + json.dumps({
        "sent": True, "status": "timeout", "cost_usd": None, "usage": None, "wall_ms": 10,
        "budget_request": False,
    }) + "\n")


def test_continue_simplify_stop_and_cross_model(tmp_path: Path):
    continue_dir = tmp_path / "qwen"
    simplify_dir = tmp_path / "gemma"
    _write(
        continue_dir, "qwen3.8:27b",
        _scores(structured=0.80, summary=0.70, majority=0.55, raw=0.72, demo=0.60, none=0.58, diff=0.10, boot=[0.02, 0.18], ceiling=0.83),
        _predictions("STRUCTURED"), wall=100,
    )
    _write(
        simplify_dir, "gemma4:12b",
        _scores(structured=0.60, summary=0.70, majority=0.55, raw=0.62, demo=0.50, none=0.58, diff=-0.10, boot=[-0.20, -0.01], ceiling=0.80),
        _predictions(), wall=250,
    )
    text = render_report([load_run(continue_dir), load_run(simplify_dir)])
    assert text.startswith("# Twin-2K-500 result")
    assert "Headline decision: inconclusive." in text
    assert "models disagree" in text
    assert "qwen3.8:27b" in text and "gemma4:12b" in text
    assert "0.83" in text and "0.56" in text
    assert "Unsure is an abstention" in text
    # superseded retry is not in the known-cost path; both models still list one counted call
    assert "Mean wall ms" in text
    qwen = load_run(continue_dir)
    assert decide_one(qwen)["decision"] == "continue"
    assert decide_one(load_run(simplify_dir))["decision"] == "simplify"
    unsure = [line for line in text.splitlines() if line.startswith("| STRUCTURED |")]
    assert unsure and "0.500" in unsure[0]

    stop_dir = tmp_path / "stop"
    _write(
        stop_dir, "stop-model",
        _scores(structured=0.50, summary=0.49, majority=0.50, raw=0.50, demo=0.50, none=0.40, diff=0.01, boot=[-0.05, 0.04], ceiling=0.90),
        _predictions(), wall=10,
    )
    assert decide_one(load_run(stop_dir))["decision"] == "stop"

    broken = tmp_path / "broken"
    _write(
        broken, "broken",
        _scores(structured=0.8, summary=0.7, majority=0.5, raw=0.7, demo=0.6, none=0.5, diff=0.1, boot=[0.02, 0.2], ceiling=0.8),
        [row for row in _predictions() if row["arm"] != "RAW"], wall=10,
    )
    assert decide_one(load_run(broken))["decision"] == "inconclusive"

    out = tmp_path / "result.md"
    rc = main(["twin2k-report", "--run", str(continue_dir), "--run", str(simplify_dir), "--out", str(out)])
    assert rc == 0
    body = out.read_text(encoding="utf-8")
    assert "does not call a model" in body
    assert "Negative results:" in body
