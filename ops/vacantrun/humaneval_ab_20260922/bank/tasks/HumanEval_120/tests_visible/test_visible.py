"""Visible checks for HumanEval_120 — a strict SUBSET of the official HumanEval test.

Rendered from HumanEval.jsonl.gz (openai/human-eval, MIT) by build.py.
The official full test is the hidden ruler and never enters this workspace.
"""

import solution


def check_visible_01():
    candidate = solution.maximum
    assert candidate([-3, -4, 5], 3) == [-4, -3, 5]

def check_visible_02():
    candidate = solution.maximum
    assert candidate([4, -4, 4], 2) == [4, 4]
