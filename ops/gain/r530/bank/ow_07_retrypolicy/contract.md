# Contract

    solution.retry(fn, *, attempts: int, backoff_s: float, max_backoff_s: float,
                   retry_on: tuple[type[BaseException], ...],
                   sleep: Callable[[float], None]) -> Any

- `fn` takes no arguments. `retry` returns the value of the first call that
  returns.
- `fn` is called at most `attempts` times.
- After the k-th failure, counting from 1, the helper waits
  `min(backoff_s * 2 ** (k - 1), max_backoff_s)` seconds by calling `sleep` with
  that number.
- After the final failure there is no wait; the exception `fn` raised is raised
  onward, the same object, not wrapped in anything.
- An exception that is not an instance of any type in `retry_on` is raised onward
  at once: no further call, no wait. An empty `retry_on` therefore retries
  nothing.
- `attempts < 1` raises `ValueError` before `fn` is called.
