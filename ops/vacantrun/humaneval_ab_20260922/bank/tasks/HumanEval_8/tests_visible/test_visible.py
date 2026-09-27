"""Visible checks for HumanEval_8 — a strict SUBSET of the official HumanEval test.

Rendered from HumanEval.jsonl.gz (openai/human-eval, MIT) by build.py.
The official full test is the hidden ruler and never enters this workspace.
"""

import solution


def check_visible_01():
    candidate = solution.sum_product
    assert candidate([]) == (0, 1)

def check_visible_02():
    candidate = solution.sum_product
    assert candidate([1, 1, 1]) == (3, 1)
