# Contract

Put your work in `solution.py` (or a package directory `solution/`) in this
directory. Nothing else is imported.

## Interface

`solution.RateLimiter(window_s, max_events, clock)` — all three positional.

- `window_s: float` — how long the window is, in seconds.
- `max_events: int` — how many events are allowed inside one window.
- `clock: Callable[[], float]` — called with no arguments, returns "now" as a
  float number of seconds. Nothing in this class may call `time.time()`,
  `time.monotonic()` or `time.sleep()`.

Methods:

- `.allow(key: str) -> bool` — `True` when the request is permitted. **It records
  an event only when it returns `True`.** A rejected request is not recorded, so
  calling `.allow` twice in a row on a blocked key does not push the window.
- `.retry_after(key: str) -> float` — `0.0` when `.allow(key)` would return
  `True` right now; otherwise the number of seconds that must pass before
  `.allow(key)` would return `True`. When nothing can ever be allowed, this is
  `float("inf")`.
- `.reset(key: str | None = None) -> None` — forget the events for that key;
  `None` means forget every key.

## The window

An event counts toward the limit when its timestamp `t` satisfies

```
now - window_s < t <= now
```

That is: **left-open, right-closed**. An event whose timestamp is exactly
`now - window_s` has fallen out. An event whose timestamp is later than `now`
(which can happen if the clock goes backwards) does not count either.

Keys are independent: events under one key never affect another key.

## Validation

`window_s <= 0` or `max_events < 0` raises `ValueError` from the constructor.
`max_events == 0` is valid and means nothing is ever allowed.
