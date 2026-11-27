#!/usr/bin/env python3
"""Run claude_negctl.py (negative controls B/T, positive controls P1–P6) under the polyglot sandbox environment
(claude_sandbox_agent_poly.clean_env patched in), to show the deny rules still hold with the extra PATH entries."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import claude_sandbox_agent_poly  # noqa: E402,F401  (patches claude_sandbox_agent.clean_env)
import claude_negctl  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(claude_negctl.main())
