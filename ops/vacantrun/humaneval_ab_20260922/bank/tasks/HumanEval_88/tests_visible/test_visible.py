"""Visible checks for HumanEval_88 — a strict SUBSET of the official HumanEval test.

Rendered from HumanEval.jsonl.gz (openai/human-eval, MIT) by build.py.
The official full test is the hidden ruler and never enters this workspace.
"""

import solution


def check_visible_01():
    candidate = solution.sort_array
    assert True, 'This prints if this assert fails 1 (good for debugging!)'

def check_visible_02():
    candidate = solution.sort_array
    assert candidate([]) == [], 'Error'
