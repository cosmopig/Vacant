"""Visible checks for HumanEval_0 — a strict SUBSET of the official HumanEval test.

Rendered from HumanEval.jsonl.gz (openai/human-eval, MIT) by build.py.
The official full test is the hidden ruler and never enters this workspace.
"""

import solution


def check_visible_01():
    candidate = solution.has_close_elements
    assert candidate([1.0, 2.0, 3.9, 4.0, 5.0, 2.2], 0.3) == True

def check_visible_02():
    candidate = solution.has_close_elements
    assert candidate([1.0, 2.0, 3.9, 4.0, 5.0, 2.2], 0.05) == False
