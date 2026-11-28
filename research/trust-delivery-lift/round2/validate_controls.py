#!/usr/bin/env python3
"""Run must-match / must-differ controls (zero model cost)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from typed_value import assert_controls, control_suite

# Legacy invoice visible checks still use scorer path
sys.path.insert(0, str(Path(__file__).parent.parent))
from scorer import assert_scorer_controls  # noqa: E402


def main() -> None:
    assert_controls()
    assert_scorer_controls()
    suite = control_suite()
    out = Path(__file__).parent / "data" / "control_extraction_results.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"passed": True, "n": len(suite), "cases": suite}, indent=2), encoding="utf-8")
    print(f"control_extraction: {len(suite)} cases OK -> {out}")


if __name__ == "__main__":
    main()