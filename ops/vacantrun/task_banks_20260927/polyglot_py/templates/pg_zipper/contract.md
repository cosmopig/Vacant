# Contract

Write your solution to `zipper.py` in the root of this workspace. The file does not exist
yet; create it. Start from this skeleton and keep these names, because the tests import them:

```python
class Zipper:
    @staticmethod
    def from_tree(tree):
        pass

    def value(self):
        pass

    def set_value(self):
        pass

    def left(self):
        pass

    def set_left(self):
        pass

    def right(self):
        pass

    def set_right(self):
        pass

    def up(self):
        pass

    def to_tree(self):
        pass
```

- Put all of your code in `zipper.py`. Only use the Python standard library; do not
  install packages.
- Don't change the names of existing functions or classes, as they may be referenced from
  other code like unit tests.
- The tests for this task are in `zipper_test.py`. The tests are correct; don't change them. Run them
  with:

      python3 -m pytest -q zipper_test.py

  or, without pytest:

      python3 -m unittest zipper_test.py
