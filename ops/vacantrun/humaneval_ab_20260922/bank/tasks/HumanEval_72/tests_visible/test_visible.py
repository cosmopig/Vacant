"""Visible checks for HumanEval_72 — a strict SUBSET of the official HumanEval test.

Rendered from HumanEval.jsonl.gz (openai/human-eval, MIT) by build.py.
The official full test is the hidden ruler and never enters this workspace.
"""

import solution


def check_visible_01():
    candidate = solution.will_it_fly
    assert candidate([3, 2, 3], 9) is True

def check_visible_02():
    candidate = solution.will_it_fly
    assert candidate([1, 2], 5) is False
