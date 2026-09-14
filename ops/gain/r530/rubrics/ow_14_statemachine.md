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

**Readability** -- 1: a class with `self.s`, `self.h`, `self.t` and `fire`
written as a chain of `if event == ...`. 3: readable, but the validation is a
nested double loop inline in `__init__`. 5: `Machine` with `state`, `history` and a
`validate(spec, start)` helper; the one comment explains why a self-transition is
still appended.

**Structure** -- 1: `can` and `fire` each look the event up in their own way.
3: `fire` calls `can` but the history append happens in two places. 5: one lookup
helper, one place that records a move, so a new kind of move cannot forget the
record.

**Error handling** -- 1: a refused event silently leaves the state alone and
returns None. 3: `ValueError("bad event")`. 5: `ValueError("state 'paid' has no
event 'cancel'")` naming both halves, and separate constructor errors naming the
undefined target or the unknown start.

**Fit to goal** -- 1: no history at all. 3: moves and history right, but a refused
event still lands in the history. 4: everything but the copy on the way out.
5: refusal leaving state and record untouched, self-transitions recorded, rules
validated at hand-over, history copied on the way out, and reset returning both
state and record to the beginning.
