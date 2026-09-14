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

**Readability** -- 1: one `parse` of 150 lines with `l`, `k`, `v`, `cur` and the
comment stripping done by `split("#")[0]`. 3: values parsed by a separate function
but the string scanner is written once for comments and again for arrays.
5: `strip_comment`, `parse_value`, `parse_string` and `dump_value` read like their
names, and the one comment explains why comment stripping has to know about quotes.

**Structure** -- 1: `dumps` is a second, independent idea of the format that drifts
from `parse`. 3: both exist but the list rules are written twice. 5: one place
states what a value may be, used when reading and when writing, so the round trip
cannot rot.

**Error handling** -- 1: a malformed line is skipped, so half a config silently
disappears. 3: `ValueError` raised without the line number. 5: every message begins
`line 7: ` and says what it found, which is exactly what a person editing the file
by hand needs.

**Fit to goal** -- 1: everything read as a string, so numbers and booleans come out
as text. 3: values and headings right, but a `#` inside text truncates the value.
5: five kinds, nested headings, comment-aware scanning, escapes, duplicates caught
with line numbers, and both round-trip properties.
