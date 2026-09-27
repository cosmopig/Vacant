# Contract

Write your solution to `grep.py` in the root of this workspace. The file does not exist
yet; create it. Start from this skeleton and keep these names, because the tests import them:

```python
def grep(pattern, flags, files):
    pass
```

- Put all of your code in `grep.py`. Only use the Python standard library; do not
  install packages.
- Don't change the names of existing functions or classes, as they may be referenced from
  other code like unit tests.
- The tests for this task are in `grep_test.py`. The tests are correct; don't change them. Run them
  with:

      python3 -m pytest -q grep_test.py

  or, without pytest:

      python3 -m unittest grep_test.py
