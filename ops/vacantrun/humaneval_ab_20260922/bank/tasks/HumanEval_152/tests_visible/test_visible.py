"""Visible checks for HumanEval_152 — a strict SUBSET of the official HumanEval test.

Rendered from HumanEval.jsonl.gz (openai/human-eval, MIT) by build.py.
The official full test is the hidden ruler and never enters this workspace.
"""

import solution


def check_visible_01():
    candidate = solution.compare
    assert candidate([1, 2, 3, 4, 5, 1], [1, 2, 3, 4, 2, -2]) == [0, 0, 0, 0, 3, 3], 'This prints if this assert fails 1 (good for debugging!)'

def check_visible_02():
    candidate = solution.compare
    assert candidate([0, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0]) == [0, 0, 0, 0, 0, 0], 'This prints if this assert fails 1 (good for debugging!)'
