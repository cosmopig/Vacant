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

This is a loose-contract task: the contract fixes only the entry points and
the return types, and the goal states the properties that matter. The scale
above is the one every R530 task uses, unweighted (prereg S1-4); what changes
here is only what the examples below look like.

**Readability** -- 1: one function with `d`, `s`, `r`, `tmp` and a while loop whose
exit condition needs tracing. 3: readable, but the tie-break between two jobs that
are both ready is an accident of dictionary order rather than a stated choice.
5: the tie-break is a named, commented decision, so the "same table gives the same
order" property is visible rather than incidental.

**Structure** -- 1: the circle check, the ordering and the
collection of prerequisite-only jobs are one loop with three flags. 3: split, but
the set of all jobs is derived twice with slightly different rules. 5: one place
answers "what are all the jobs", one place answers "what is ready now", and the
circle is detected as the absence of anything ready rather than by a second
traversal.

**Error handling** -- 1: a circle makes it loop forever or blow the recursion
limit. 3: `ValueError` raised on a circle. 5: `ValueError("these jobs wait on each
other in a circle: build, test")` naming the jobs still stuck, which is what the
person reading the build log needs.

**Fit to goal** -- 1: returns the keys in whatever order they were
in. 3: a correct order, but jobs that appear only as prerequisites are dropped.
5: all four properties deliberately answered, with the determinism coming from a
stated rule rather than from the input happening to be ordered.
