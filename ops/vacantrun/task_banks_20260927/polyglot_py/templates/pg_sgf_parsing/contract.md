# Contract

Write your solution to `sgf_parsing.py` in the root of this workspace. The file does not exist
yet; create it. Start from this skeleton and keep these names, because the tests import them:

```python
class SgfTree:
    def __init__(self, properties=None, children=None):
        self.properties = properties or {}
        self.children = children or []

    def __eq__(self, other):
        if not isinstance(other, SgfTree):
            return False
        for key, value in self.properties.items():
            if key not in other.properties:
                return False
            if other.properties[key] != value:
                return False
        for key in other.properties.keys():
            if key not in self.properties:
                return False
        if len(self.children) != len(other.children):
            return False
        for child, other_child in zip(self.children, other.children):
            if child != other_child:
                return False
        return True

    def __ne__(self, other):
        return not self == other


def parse(input_string):
    pass
```

- Put all of your code in `sgf_parsing.py`. Only use the Python standard library; do not
  install packages.
- Don't change the names of existing functions or classes, as they may be referenced from
  other code like unit tests.
- The tests for this task are in `sgf_parsing_test.py`. The tests are correct; don't change them. Run them
  with:

      python3 -m pytest -q sgf_parsing_test.py

  or, without pytest:

      python3 -m unittest sgf_parsing_test.py
