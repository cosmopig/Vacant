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

**Readability** -- 1: one `summarize` of 120 lines with `d`, `t`, `b`, `q` and
percentile arithmetic inlined twice. 3: parsing split out but the percentile index
is written as a bare expression the reader has to verify by hand. 5:
`parse_line`, `percentile(values, p)` and an accumulator whose fields are named;
the one comment explains why nearest-rank uses a 1-based rank.

**Structure** -- 1: reading, validating, bucketing and formatting all in one pass
with flags. 3: parsing separated but p50 and p95 are computed by two near-identical
blocks. 5: one `percentile` used twice, one accumulator type, and the CLI is a thin
presenter over `summarize`.

**Error handling** -- 1: a garbled line raises and the run dies. 3: bad lines are
caught by a broad `except` that also hides real bugs. 5: a line is validated by an
explicit shape check, the failure is counted rather than raised, and the count is
reported so the client can watch it.

**Fit to goal** -- 1: counts only, no error share, no percentiles. 3: all three
numbers present but the error share includes the four-hundreds. 5: five-hundreds
only, nearest-rank percentiles, busiest first with a stable tie-break, blank lines
ignored, bad lines counted, and a readable table from the shell.
