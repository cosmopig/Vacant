# Contract

Write your answer in `solution.py` at the root of this workspace.

- Define a top-level function named `resultsArray`. Not a method, not a class.
- It is called positionally: `resultsArray(*args)`. The checks pass the arguments
  in the order the task statement gives them.
- It must **return** the answer. Printing is not returning; anything written to
  stdout is ignored.
- Standard library only. No network, no file system, no installed packages.
- A returned value counts as correct when it compares equal under this rule:
  plain `==` first; `True`/`False` never compare equal to `1`/`0`; two numbers
  are equal within 1e-6; lists and tuples are compared element by element,
  recursively, and must have the same length.

The checks that ship with this task are in `tests_visible/`. Run them with:

    sh run_tests.sh

Each failure prints `args=... got=... want=...` for the first case that failed.
