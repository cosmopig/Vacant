# Contract

    solution.RateLimiter(window_s: float, max_events: int, clock: Callable[[], float])
    .allow(key: str) -> bool
    .retry_after(key: str) -> float
    .reset(key: str | None = None) -> None

- `clock()` returns the current time in seconds as a float, and is the only
  source of time the limiter may use.
- The window slides: an event counts while it falls in `(now - window_s, now]`,
  left open and right closed.
- `allow(key)` returns True when the number of counted events for that key is
  below `max_events`, and records the event. A denied call records nothing, so
  being denied ten times in a row leaves the same state as being denied once.
- Events are counted per key; a key that has never been seen has no events.
- `retry_after(key)` returns `0.0` whenever the next `allow(key)` would succeed.
  Otherwise it returns `leaving + window_s - now`, where `leaving` is the
  earliest counted event that has to fall out of the window before the next call
  can be admitted. When `max_events` is 0 no wait ever helps, so `retry_after`
  returns `float("inf")`.
- `reset(key)` forgets the events of that key; `reset()` and `reset(None)` forget
  everything.
- A clock that moves backwards is not an error: events lying in the future are
  simply outside `(now - window_s, now]`.
- `window_s <= 0` or `max_events < 0` raises `ValueError` from the constructor.
