#!/usr/bin/env python3
"""寫出固定提示詞模板到 ops/redo/exams_haiku_20261127/prompts/（逐字存檔；佔位符 {GOAL} {MODULE} {STUB} {MISTAKE_KIND}）。"""
import json
import pathlib

OUT = pathlib.Path(__file__).resolve().parents[1] / "exams_haiku_20261127" / "prompts"
OUT.mkdir(parents=True, exist_ok=True)

head = """You are writing an acceptance test file (pytest) for a programming exercise. You are given only the exercise's requirements text and the stub file of the solution module. A solution will be written later by someone else, and your file will be run against it.

=== Requirements text ===
{GOAL}
=== End of requirements text ===

=== Stub file {MODULE}.py ===
{STUB}
=== End of stub file ===

"""
common = """- Import from the module `{MODULE}` exactly as `from {MODULE} import ...`, using the names in the stub file.
- Expected values must be worked out by you from the requirements text; never obtained by calling a solution.
- Only check behaviour that the requirements text states or clearly implies.
- Standard library and pytest only. Deterministic. No network, no files outside a temporary directory.
- Output only the complete Python file inside one ```python code block, and nothing else.
"""
xm = head + """Write a single pytest file made of input/output tests.
- Use plain `assert` statements on input/output pairs, in `test_` functions.
- Write at least 8 assertions in total, covering the rules and the boundary cases stated in the requirements text.
""" + common
xmv = head + """Write a single pytest file made of input/output tests, where every assertion is traced to the requirements text.
- Use plain `assert` statements on input/output pairs, in `test_` functions.
- Write at least 8 assertions in total, covering the rules and the boundary cases stated in the requirements text.
- Directly above each `assert` statement (or each `with pytest.raises(...)` block) put one comment line of exactly this form, quoting one sentence or example from the requirements text character for character (a single line, without line breaks inside the quote):
  # SRC: "<quoted text copied from the requirements text>"
  The quote must be an exact substring of the requirements text that justifies that assertion. Use a separate comment line for each assertion even when the quote repeats.
""" + common
pb = head + """Write a single pytest file that checks the requirements as separate properties.
- First split the requirements text into separately checkable properties: input and output types and format, invariants, boundary behaviour that the text states, and the examples the text gives.
- Write one independent check function per property. Each check function is a `test_` function that makes its own calls (no shared mutable state between check functions), with plain `assert` statements.
- Give each check function a docstring that starts with `REQ: "<quoted requirement sentence>"`, quoting the sentence or example from the requirements text that the property comes from.
- Write at least 8 check functions if the text supports that many properties; otherwise write as many as it supports.
""" + common
wrong = head + """Write a Python implementation of the module `{MODULE}` (the file {MODULE}.py) that follows the stub file's names and signatures. The implementation should look realistic and work for most ordinary inputs, but contain exactly one realistic, subtle mistake of this kind: {MISTAKE_KIND}.
- Do not add comments or anything else that points at the mistake.
- Standard library only.
- Output only the complete Python file inside one ```python code block, and nothing else.
"""
kinds = {
    "1": "a boundary or off-by-one error, or wrong handling of an empty or minimal input",
    "2": "misreading one of the rules stated in the requirements text, so that one stated rule is applied differently from what the text says",
    "3": "a wrong order, format, or type of the returned output (while the values are otherwise right)",
    "4": "mishandling of a rarely considered case such as repeated input, state kept between calls, an error that should be raised, or a special-value case",
}
for n, t in [("xm", xm), ("xmv", xmv), ("pb", pb), ("wrong", wrong)]:
    (OUT / f"{n}_prompt.txt").write_text(t, encoding="utf-8")
(OUT / "wrong_kinds.json").write_text(json.dumps(kinds, indent=1, ensure_ascii=False), encoding="utf-8")
