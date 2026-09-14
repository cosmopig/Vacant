# Qualitative rubric (blind scoring)

Four dimensions, 1-5 each. The scale below is shared by every R530 task
(prereg S1-4); the worked examples at the bottom are specific to this task.

| Dim | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| **Readability** | Names carry no meaning; no comments and none would help; a single function runs past 80 lines | Readable only by tracing execution by hand; names abbreviated past recognition | Names roughly say what they hold; the shape is followable but a few passages need re-reading | Reads straight through with one or two pauses; comments mostly explain "why" | Reads once and is understood; names use the same words as the contract; comments appear only where "why" is not obvious from the code |
| **Structure** | Everything in one function or one tangle; the pieces cannot be moved | Split exists but each piece knows the internals of the others | Split exists but boundaries are arbitrary; duplicated logic appears twice or more | Clear units, at most one seam that feels accidental | One responsibility per unit; no duplicated logic; adding one new rule means editing one place |
| **Error handling** | Exception messages do not say what went wrong; or a bare `except:` swallows failures | Errors surface but as the wrong type, or the message names the module rather than the input | Every exception the contract asks for is raised, message acceptable | Messages name the offending input in most paths | Every exception the contract asks for is raised; messages name which part of the input is at fault; nothing is swallowed; the normal path is not written as exception flow |
| **Fit to goal** | What it does does not line up with the trouble the goal describes | Only the happy path from the goal is addressed | The contract is met, but only part of the trouble in the goal is handled | Nearly all of the goal's trouble is visibly handled | Every piece of trouble named in the goal has something visible in the code that answers it |

> Note (prereg S1-4): **Fit to goal** is the one dimension that partly overlaps
> the hidden checks, so it is necessarily correlated with the quantitative
> outcome and must never be cited as independent qualitative corroboration.

## Worked examples for this task

**Readability** -- 1: one class with `self.d`, `self.w`, `self.m` and a 90-line
`allow`. 3: readable methods, but the window arithmetic is repeated inline in both
`allow` and `retry_after`. 5: a named helper such as `counted_events(key, now)`
used by both, and the one comment explains why the window is left-open rather
than restating the comparison.

**Structure** -- 1: `allow` also does the pruning, the config validation and the
retry arithmetic. 3: pruning split out but the "is this event inside the window"
rule is written twice with different comparisons. 5: one place decides membership
of the window; `allow` and `retry_after` both go through it, so they cannot drift.

**Error handling** -- 1: a bad `window_s` silently becomes a limiter that never
admits anything. 3: `ValueError("bad config")` from the constructor. 5:
`ValueError("window_s must be positive, got -1")`, raised at construction, naming
which argument is wrong.

**Fit to goal** -- 1: reads the real clock, so the client's tests would have to
sleep. 3: injected clock honoured, but `retry_after` returns the window length as
a fixed guess. 5: injected clock only; the wait shrinks as the clock advances;
repeated denials do not extend it; a rewound clock and fractional seconds both
behave; `reset` covers one caller and everybody.
