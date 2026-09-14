# Goal

A client's code calls things that fail intermittently. They want a helper that
re-runs a call a few times before giving up, backing off longer each time, but
only for the kinds of failure that are worth retrying. Their tests must run
instantly, so waiting has to be something they can substitute.

A failure that is not worth retrying has to come straight back out, immediately,
with no pause at all. A subclass of a listed error counts as that error.

When the last attempt fails they want the original error, not something the helper
wrapped around it, and they do not want to sit through a pause that leads nowhere.

The delay must stop growing once it reaches a ceiling they set, because doubling
forever is how one of their jobs slept for an hour. Asking for fewer than one
attempt is a programming mistake and should be caught before anything is called.

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
