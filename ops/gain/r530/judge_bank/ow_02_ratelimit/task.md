# Goal

A client's service gets hammered by bursts from the same callers. They want a
piece of code they can put in front of it that says yes or no to each request,
configured by how long a window is and how many calls are allowed in that window,
counted separately per caller.

When it says no, the caller wants to know how long to wait before trying again,
and that answer has to shrink as time passes rather than being a fixed guess.
Being turned away repeatedly must not push the wait further out.

Their tests must not sleep, so the notion of now has to come from outside. The
same test clock is sometimes rewound between cases, and it deals in fractions of
a second, so neither of those may blow up.

They also want to wipe the record for one caller, or for everybody, without
rebuilding the limiter, and they want a nonsensical configuration to fail at
construction rather than at the first request.

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
