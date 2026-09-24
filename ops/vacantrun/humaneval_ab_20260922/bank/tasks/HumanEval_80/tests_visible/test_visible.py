"""Visible checks for HumanEval_80 — a strict SUBSET of the official HumanEval test.

Rendered from HumanEval.jsonl.gz (openai/human-eval, MIT) by build.py.
The official full test is the hidden ruler and never enters this workspace.
"""

import solution


def check_visible_01():
    candidate = solution.is_happy
    assert candidate('a') == False, 'a'

def check_visible_02():
    candidate = solution.is_happy
    assert candidate('aa') == False, 'aa'
