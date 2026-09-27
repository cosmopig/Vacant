# Contract

Write your solution to `dot_dsl.py` in the root of this workspace. The file does not exist
yet; create it. Start from this skeleton and keep these names, because the tests import them:

```python
NODE, EDGE, ATTR = range(3)


class Node:
    def __init__(self, name, attrs):
        self.name = name
        self.attrs = attrs

    def __eq__(self, other):
        return self.name == other.name and self.attrs == other.attrs


class Edge:
    def __init__(self, src, dst, attrs):
        self.src = src
        self.dst = dst
        self.attrs = attrs

    def __eq__(self, other):
        return (self.src == other.src and
                self.dst == other.dst and
                self.attrs == other.attrs)


class Graph:
    def __init__(self, data=None):
        pass
```

- Put all of your code in `dot_dsl.py`. Only use the Python standard library; do not
  install packages.
- Don't change the names of existing functions or classes, as they may be referenced from
  other code like unit tests.
- The tests for this task are in `dot_dsl_test.py`. The tests are correct; don't change them. Run them
  with:

      python3 -m pytest -q dot_dsl_test.py

  or, without pytest:

      python3 -m unittest dot_dsl_test.py
