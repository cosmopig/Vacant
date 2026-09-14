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

**Readability** -- 1: a while loop with `i`, `n`, `b`, `m` and a nested
`try/except/else/finally`. 3: readable loop but the backoff arithmetic is inline
and the off-by-one is invisible. 5: `delay_after(failure_number)` names the rule,
so the exponent and the ceiling are stated once where a reader can check them.

**Structure** -- 1: the retry decision, the delay arithmetic and the re-raise all
tangled in one except block. 3: the delay split out, but "is this worth retrying"
is asked in two places. 5: one place decides retryability, one place computes the
delay, and the loop reads as attempt, decide, wait.

**Error handling** -- 1: `except Exception` swallowing the failure and returning
None on the last attempt. 3: the original error is re-raised, but only after a
pointless final sleep. 5: `raise` with no argument so the traceback and the object
survive; `ValueError("attempts must be at least 1, got 0")` before anything runs.

**Fit to goal** -- 1: sleeps with `time.sleep`, so the client's tests are slow.
3: injected sleep honoured, but the ceiling is missing and the delay doubles
forever. 5: injected sleep, exact doubling from the first failure, the ceiling,
no trailing sleep, the unwrapped original error, subclass matching and the
attempts check all visible.
