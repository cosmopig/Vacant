"""Visible checks for HumanEval_24 — a strict SUBSET of the official HumanEval test.

Rendered from HumanEval.jsonl.gz (openai/human-eval, MIT) by build.py.
The official full test is the hidden ruler and never enters this workspace.
"""

import solution


def check_visible_01():
    candidate = solution.largest_divisor
    assert candidate(3) == 1

def check_visible_02():
    candidate = solution.largest_divisor
    assert candidate(7) == 1
