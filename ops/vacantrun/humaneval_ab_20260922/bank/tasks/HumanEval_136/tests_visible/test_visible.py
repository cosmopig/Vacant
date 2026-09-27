"""Visible checks for HumanEval_136 — a strict SUBSET of the official HumanEval test.

Rendered from HumanEval.jsonl.gz (openai/human-eval, MIT) by build.py.
The official full test is the hidden ruler and never enters this workspace.
"""

import solution


def check_visible_01():
    candidate = solution.largest_smallest_integers
    assert candidate([2, 4, 1, 3, 5, 7]) == (None, 1)

def check_visible_02():
    candidate = solution.largest_smallest_integers
    assert candidate([2, 4, 1, 3, 5, 7, 0]) == (None, 1)
