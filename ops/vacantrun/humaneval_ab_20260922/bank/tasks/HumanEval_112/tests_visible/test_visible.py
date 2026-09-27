"""Visible checks for HumanEval_112 — a strict SUBSET of the official HumanEval test.

Rendered from HumanEval.jsonl.gz (openai/human-eval, MIT) by build.py.
The official full test is the hidden ruler and never enters this workspace.
"""

import solution


def check_visible_01():
    candidate = solution.reverse_delete
    assert candidate('abcde', 'ae') == ('bcd', False)

def check_visible_02():
    candidate = solution.reverse_delete
    assert candidate('abcdef', 'b') == ('acdef', False)
