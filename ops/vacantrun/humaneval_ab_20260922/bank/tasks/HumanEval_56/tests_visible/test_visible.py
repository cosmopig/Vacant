"""Visible checks for HumanEval_56 — a strict SUBSET of the official HumanEval test.

Rendered from HumanEval.jsonl.gz (openai/human-eval, MIT) by build.py.
The official full test is the hidden ruler and never enters this workspace.
"""

import solution


def check_visible_01():
    candidate = solution.correct_bracketing
    assert candidate('<>')

def check_visible_02():
    candidate = solution.correct_bracketing
    assert candidate('<<><>>')
