"""Visible checks for HumanEval_160 — a strict SUBSET of the official HumanEval test.

Rendered from HumanEval.jsonl.gz (openai/human-eval, MIT) by build.py.
The official full test is the hidden ruler and never enters this workspace.
"""

import solution


def check_visible_01():
    candidate = solution.do_algebra
    assert candidate(['**', '*', '+'], [2, 3, 4, 5]) == 37

def check_visible_02():
    candidate = solution.do_algebra
    assert candidate(['+', '*', '-'], [2, 3, 4, 5]) == 9
