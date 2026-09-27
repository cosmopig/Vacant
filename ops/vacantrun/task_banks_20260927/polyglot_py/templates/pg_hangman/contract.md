# Contract

Write your solution to `hangman.py` in the root of this workspace. The file does not exist
yet; create it. Start from this skeleton and keep these names, because the tests import them:

```python
# Game status categories
# Change the values as you see fit
STATUS_WIN = 'win'
STATUS_LOSE = 'lose'
STATUS_ONGOING = 'ongoing'


class Hangman:
    def __init__(self, word):
        self.remaining_guesses = 9
        self.status = STATUS_ONGOING

    def guess(self, char):
        pass

    def get_masked_word(self):
        pass

    def get_status(self):
        pass
```

- Put all of your code in `hangman.py`. Only use the Python standard library; do not
  install packages.
- Don't change the names of existing functions or classes, as they may be referenced from
  other code like unit tests.
- The tests for this task are in `hangman_test.py`. The tests are correct; don't change them. Run them
  with:

      python3 -m pytest -q hangman_test.py

  or, without pytest:

      python3 -m unittest hangman_test.py
