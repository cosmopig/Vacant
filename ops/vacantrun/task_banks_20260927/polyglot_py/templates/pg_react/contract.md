# Contract

Write your solution to `react.py` in the root of this workspace. The file does not exist
yet; create it. Start from this skeleton and keep these names, because the tests import them:

```python
class InputCell:
    def __init__(self, initial_value):
        self.value = None


class ComputeCell:
    def __init__(self, inputs, compute_function):
        self.value = None

    def add_callback(self, callback):
        pass

    def remove_callback(self, callback):
        pass
    
```

- Put all of your code in `react.py`. Only use the Python standard library; do not
  install packages.
- Don't change the names of existing functions or classes, as they may be referenced from
  other code like unit tests.
- The tests for this task are in `react_test.py`. The tests are correct; don't change them. Run them
  with:

      python3 -m pytest -q react_test.py

  or, without pytest:

      python3 -m unittest react_test.py
