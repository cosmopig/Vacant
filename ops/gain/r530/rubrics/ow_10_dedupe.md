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

**Readability** -- 1: one function with `d`, `o`, `k2`, `tmp` and the three
policies as an if-chain inside two nested loops. 3: readable, but the key
extraction is written once for the string case and once for the list case.
5: `key_of(record, key)` handles both shapes in one place, and the merge rule is a
named function whose comment explains why a later None does not overwrite.

**Structure** -- 1: the policies are three near-identical copies of the same loop.
3: one loop with an if-chain; the copying of dictionaries happens in three places.
5: one loop, one place that decides what a collision does, one place that copies,
so adding a fourth policy is one branch.

**Error handling** -- 1: `record[key]` left to raise a bare KeyError from deep
inside, or `record.get(key)` so that missing fields all collapse onto None.
3: KeyError and ValueError both raised, messages generic. 5: `KeyError("email")`
naming the field, and `ValueError("policy must be one of first, last, merge, got
'newest'")` naming the bad value and the alternatives.

**Fit to goal** -- 1: a set of keys, so the order things first appeared is lost.
3: order and policies right, but the result aliases the caller's dictionaries.
5: order, three policies, composite keys compared part by part, None treated as
not filled in, the loud KeyError, and no input touched.
