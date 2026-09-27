# Contract

Write your solution to `list_ops.py` in the root of this workspace. The file does not exist
yet; create it. Start from this skeleton and keep these names, because the tests import them:

```python
def append(list1, list2):
    pass


def concat(lists):
    pass


def filter(function, list):
    pass


def length(list):
    pass


def map(function, list):
    pass


def foldl(function, list, initial):
    pass


def foldr(function, list, initial):
    pass


def reverse(list):
    pass
```

- Put all of your code in `list_ops.py`. Only use the Python standard library; do not
  install packages.
- Don't change the names of existing functions or classes, as they may be referenced from
  other code like unit tests.
- The tests for this task are in `list_ops_test.py`. The tests are correct; don't change them. Run them
  with:

      python3 -m pytest -q list_ops_test.py

  or, without pytest:

      python3 -m unittest list_ops_test.py
