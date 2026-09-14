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

**Readability** -- 1: two functions of if-chains over `s[-3:]`, `s[-2:]` and
`s[-1:]` with magic 1024s scattered through. 3: a unit table exists but the binary
and decimal cases are still two parallel blocks. 5: one table mapping a lowercase
unit to its step, one loop that walks up the units, and the one comment explains
why bytes are printed without a decimal.

**Structure** -- 1: `humanize` re-derives the factors that `to_bytes` already
knows. 3: a shared table but the two unit families are hard-coded twice.
5: the two families are two tuples driven by the same code, so the binary flag
selects data rather than branching logic.

**Error handling** -- 1: `int(s[:-2])` raising whatever it raises, or a silent
fallback to zero. 3: `ValueError` for bad input, message generic. 5:
`ValueError("unknown unit 'KBs' in '4 KBs'")` naming the offending piece, and the
negative case refused from both entry points.

**Fit to goal** -- 1: KB and KiB treated as the same thing. 3: the two bases right
but the printed form drops the trailing `.0`. 5: both bases, case-insensitive
units, optional space, truncation rather than rounding, the whole-number byte form,
growth past the largest unit, and every refusal the goal lists.
