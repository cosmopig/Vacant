import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import metrics  # noqa: E402
import trajectory  # noqa: E402


def test_bash_classification():
    assert trajectory.classify_bash("python -m pytest -q") == "T"
    assert trajectory.classify_bash("cat pricing.py") == "R"
    assert trajectory.classify_bash("ls -R") == "S"
    assert trajectory.classify_bash("grep -rn foo .") == "S"
    assert trajectory.classify_bash("git diff") == "S"
    assert trajectory.classify_bash("echo hi > a.txt") == "E"
    assert trajectory.classify_bash("python3 report.py week.json") == "X"


def test_similarity_bounds():
    assert metrics.edit_similarity("SRTETF", "SRTETF") == 1.0
    assert metrics.edit_similarity("", "") == 1.0
    assert metrics.edit_similarity("REF", "A") == 0.0
    assert 0 < metrics.lcs_similarity("SRTETF", "REF") < 1
    assert metrics.collapse("RRRSSE") == "RSE"


def _ev(content, role="assistant"):
    return {"type": "message_end", "message": {"role": role, "content": content, "timestamp": 1000}}


def test_normalize_and_features():
    events = [
        _ev([{"type": "text", "text": "Look first."}, {"type": "toolCall", "id": "1", "name": "read", "arguments": {"path": "a.py"}}]),
        {"type": "tool_execution_end", "toolCallId": "1", "isError": False},
        _ev([{"type": "toolCall", "id": "2", "name": "edit", "arguments": {"path": "a.py", "edits": []}}]),
        {"type": "tool_execution_end", "toolCallId": "2", "isError": False},
        _ev([{"type": "toolCall", "id": "3", "name": "bash", "arguments": {"command": "pytest"}}]),
        {"type": "tool_execution_end", "toolCallId": "3", "isError": True},
        _ev([{"type": "text", "text": "Done."}]),
    ]
    steps = trajectory.normalize(events, "r", "t", "baseline")
    assert metrics.action_sequence(steps) == "RETF"
    f = metrics.order_features(steps)
    assert f["read_before_first_edit"] and f["test_after_last_edit"] and not f["test_before_first_edit"]
    assert f["edited_files_were_read_first"] is True
    assert f["n_tool_errors"] == 1
    c = metrics.compare(steps, {"sequence": "RETF", "features": {"asked_before_acting": False}})
    assert c["edit_sim"] == 1.0 and c["feature_agreement"] == 1.0


def test_question_final_is_ask():
    steps = trajectory.normalize([_ev([{"type": "text", "text": "Which delimiter do you want?"}])], "r", "t", "b")
    assert metrics.action_sequence(steps) == "A"


def test_example_personas_are_labelled_synthetic():
    p = json.loads((Path(__file__).resolve().parents[1] / "personas" / "examples.json").read_text())
    assert "SYNTHETIC" in p["_label"]
    assert all(k.startswith("example_") for k in p["personas"])
