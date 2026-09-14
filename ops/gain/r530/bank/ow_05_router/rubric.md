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

**Readability** -- 1: one regex built by string concatenation inside `match`,
with `p`, `s`, `r` and a comment-free 90-line body. 3: pattern parsing split out
but the three segment kinds are recognised by ad hoc `startswith` checks scattered
around. 5: a named segment type with a rank, `parse_pattern`, `match_segments` and
`more_specific` reading like their names.

**Structure** -- 1: `add` stores raw strings and `match` re-parses them on every
request. 3: parsed once, but the specificity rule is expressed both as a sort key
and as an if-chain. 5: one comparison function is the single definition of "more
specific", used by both the duplicate check and the winner selection.

**Error handling** -- 1: a bad pattern becomes a regex that never matches and is
never reported. 3: `ValueError` raised for bad patterns with a generic message.
5: `ValueError("a {name:*} segment may only appear last: '/a/{r:*}/b'")` raised
from `add`, so the mistake surfaces at registration as the goal asks.

**Fit to goal** -- 1: first registered wins, so the answer depends on import order.
3: specificity handled for literal versus parameter but the catch-all is compared
by counting literals. 5: the leftmost-difference rule, order independence,
registration-time validation, the rest-of-path capture and the None-versus-empty-
dict distinction all have a visible answer.
