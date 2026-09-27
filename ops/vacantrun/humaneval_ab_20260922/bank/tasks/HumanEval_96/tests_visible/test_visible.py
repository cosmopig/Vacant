"""Visible checks for HumanEval_96 — a strict SUBSET of the official HumanEval test.

Rendered from HumanEval.jsonl.gz (openai/human-eval, MIT) by build.py.
The official full test is the hidden ruler and never enters this workspace.
"""

import solution


def check_visible_01():
    candidate = solution.count_up_to
    assert candidate(5) == [2, 3]

def check_visible_02():
    candidate = solution.count_up_to
    assert candidate(6) == [2, 3, 5]
