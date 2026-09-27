# Contract

Write your solution to `grade_school.py` in the root of this workspace. The file does not exist
yet; create it. Start from this skeleton and keep these names, because the tests import them:

```python
class School:
    def __init__(self):
        pass

    def add_student(self, name, grade):
        pass

    def roster(self):
        pass

    def grade(self, grade_number):
        pass

    def added(self):
        pass
```

- Put all of your code in `grade_school.py`. Only use the Python standard library; do not
  install packages.
- Don't change the names of existing functions or classes, as they may be referenced from
  other code like unit tests.
- The tests for this task are in `grade_school_test.py`. The tests are correct; don't change them. Run them
  with:

      python3 -m pytest -q grade_school_test.py

  or, without pytest:

      python3 -m unittest grade_school_test.py
