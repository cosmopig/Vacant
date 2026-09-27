# Contract

Write your solution to `simple_linked_list.py` in the root of this workspace. The file does not exist
yet; create it. Start from this skeleton and keep these names, because the tests import them:

```python
class EmptyListException(Exception):
    pass


class Node:
    def __init__(self, value):
        pass

    def value(self):
        pass

    def next(self):
        pass


class LinkedList:
    def __init__(self, values=None):
        pass

    def __iter__(self):
        pass

    def __len__(self):
        pass

    def head(self):
        pass

    def push(self, value):
        pass

    def pop(self):
        pass

    def reversed(self):
        pass
```

- Put all of your code in `simple_linked_list.py`. Only use the Python standard library; do not
  install packages.
- Don't change the names of existing functions or classes, as they may be referenced from
  other code like unit tests.
- The tests for this task are in `simple_linked_list_test.py`. The tests are correct; don't change them. Run them
  with:

      python3 -m pytest -q simple_linked_list_test.py

  or, without pytest:

      python3 -m unittest simple_linked_list_test.py
