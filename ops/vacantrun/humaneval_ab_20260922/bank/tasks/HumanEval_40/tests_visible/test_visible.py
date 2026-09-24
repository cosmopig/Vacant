"""Visible checks for HumanEval_40 — a strict SUBSET of the official HumanEval test.

Rendered from HumanEval.jsonl.gz (openai/human-eval, MIT) by build.py.
The official full test is the hidden ruler and never enters this workspace.
"""

import solution


def check_visible_01():
    candidate = solution.triples_sum_to_zero
    assert candidate([1, 3, 5, 0]) == False

def check_visible_02():
    candidate = solution.triples_sum_to_zero
    assert candidate([1, 3, 5, -1]) == False
