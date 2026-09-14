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

**Readability** -- 1: one function with `i`, `j`, `k`, a table called `t` and no
name for what a piece is. 3: the table is built in a named function but the
backtrack and the grouping are one 60-line loop. 5: `common_pairs`, `trim` and an
`apply` that reads as "copy up to the piece, check it, write the replacement"; the
one comment explains why a piece has to be trimmed on both sides.

**Structure** -- 1: `apply` re-derives the pieces instead of using the ones it was
given. 3: both entry points exist but the "does this piece fit here" test is
written in two places. 5: one validator used before any line is copied, so `apply`
either raises or produces a whole file, never half of one.

**Error handling** -- 1: a piece that does not fit is applied anyway, producing a
file that looks plausible and is wrong -- exactly the case the goal calls
dangerous. 3: `ValueError` raised on a mismatch, message generic. 5:
`ValueError("piece at 4 expected ['b'] but the text holds ['x']")`, plus distinct
messages for out-of-order, overlapping, oversized and malformed pieces.

**Fit to goal** -- 1: one piece covering the whole file. 3: separate pieces but
each carries unchanged context lines at its edges. 5: one piece per place that
changed, trimmed on both sides, nothing produced for an unchanged file, every
refusal case covered, inputs untouched, and repeated lines surviving the round
trip.
