# Contract

Write your solution to `paasio.py` in the root of this workspace. The file does not exist
yet; create it. Start from this skeleton and keep these names, because the tests import them:

```python
import io


class MeteredFile(io.BufferedRandom):
    """Implement using a subclassing model."""

    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def __iter__(self):
        pass

    def __next__(self):
        pass

    def read(self, size=-1):
        pass

    @property
    def read_bytes(self):
        pass

    @property
    def read_ops(self):
        pass

    def write(self, b):
        pass

    @property
    def write_bytes(self):
        pass

    @property
    def write_ops(self):
        pass


class MeteredSocket:
    """Implement using a delegation model."""

    def __init__(self, socket):
        pass

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def recv(self, bufsize, flags=0):
        pass

    @property
    def recv_bytes(self):
        pass

    @property
    def recv_ops(self):
        pass

    def send(self, data, flags=0):
        pass

    @property
    def send_bytes(self):
        pass

    @property
    def send_ops(self):
        pass
```

- Put all of your code in `paasio.py`. Only use the Python standard library; do not
  install packages.
- Don't change the names of existing functions or classes, as they may be referenced from
  other code like unit tests.
- The tests for this task are in `paasio_test.py` and `test_utils.py`. The tests are correct; don't change them. Run them
  with:

      python3 -m pytest -q paasio_test.py

  or, without pytest:

      python3 -m unittest paasio_test.py
