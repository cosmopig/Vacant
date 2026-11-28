import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "research" / "trust-delivery-lift" / "scorer.py"


def _load():
    spec = importlib.util.spec_from_file_location("tdl_scorer", MOD)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["tdl_scorer"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_synthetic_controls():
    mod = _load()
    mod.assert_scorer_controls()


def test_whole_success_requires_all_fields():
    mod = _load()
    task = {
        "fields": [
            {"id": "a", "type": "int", "required": True},
            {"id": "b", "type": "int", "required": True},
        ],
        "gold": {"a": "1", "b": "2"},
    }
    g = mod.grade_task(task, {"a": "1", "b": "99"})
    assert not g["whole_success"]