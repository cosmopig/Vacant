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

**Readability** -- 1: one function juggling strings with `[:10]` and `[11:]`
slicing and comparing them as text. 3: parsing split out, but merging and
subtracting each re-sort and re-validate in their own way. 5: `parse_instant`,
`normalise(spans)` and a subtract that reads as "cut each piece by each hole"; the
one comment explains why touching spans join, which is the half-open rule.

**Structure** -- 1: `subtract` re-implements merging inline. 3: both call a shared
sort but the "does this overlap" test is written three times with different
comparisons. 5: one normalise used by all three entry points, so the half-open
rule is stated once.

**Error handling** -- 1: a reversed span is silently swapped, so a data bug becomes
a plausible-looking booking. 3: `ValueError` raised for reversed spans.
5: `ValueError("span ends before it starts: ('2026-01-02', '2026-01-01')")` and a
separate message for an instant that cannot be read, both raised from the one place
that parses.

**Fit to goal** -- 1: overlapping spans double-counted in the total. 3: merge right,
but subtract cannot cut a hole out of the middle of a span. 5: unordered input,
overlap, touching, zero-length, date-only instants, mid-span holes, union totals and
the reversed-span report all visibly handled.
