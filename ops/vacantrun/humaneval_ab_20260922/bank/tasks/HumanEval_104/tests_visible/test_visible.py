"""Visible checks for HumanEval_104 — a strict SUBSET of the official HumanEval test.

Rendered from HumanEval.jsonl.gz (openai/human-eval, MIT) by build.py.
The official full test is the hidden ruler and never enters this workspace.
"""

import solution


def check_visible_01():
    candidate = solution.unique_digits
    assert candidate([15, 33, 1422, 1]) == [1, 15, 33]

def check_visible_02():
    candidate = solution.unique_digits
    assert candidate([152, 323, 1422, 10]) == []
