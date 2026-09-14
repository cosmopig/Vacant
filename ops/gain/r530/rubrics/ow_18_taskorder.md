# Qualitative rubric (blind scoring) -- LOOSE task

Four dimensions, 1-5 each. **This is a loose-contract task**: the contract fixes
only the entry points and the return types, and the goal states the properties that
matter. Almost every design decision was left to the worker, so the weighting
differs from the tight tasks.

> **Weighting (prereg amendment, Fable ruling 2026-09-13).** For a loose task the
> blind score is `readability + 2*structure + error_handling + 2*fit_to_goal`,
> because soundness of design is the thing this stratum exists to see. State the
> four raw scores as well, so the weighting can be recomputed.

| Dim | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| **Readability** | Names carry no meaning; no comments and none would help; a single function runs past 80 lines | Readable only by tracing execution by hand | Names roughly say what they hold; a few passages need re-reading | Reads straight through with one or two pauses | Reads once and is understood; the names state the design decisions the contract did not |
| **Structure (double weight)** | One tangle; no decision is visible as a decision | A split exists but the pieces know each other's internals | Split exists, boundaries arbitrary, duplicated logic | Clear units; the design choices are locatable | Each choice the contract left open is made in exactly one place and is named there, so a reviewer can disagree with it without reading the whole file |
| **Error handling** | Failures are swallowed, or the only failure mode is a crash from deep inside a library | Errors surface but as the wrong kind, or unlabelled | The failures the goal names are raised | Messages name the offending input | The failures the goal names are raised, the messages name what was wrong with which input, and nothing else is turned into an error that the goal did not ask to be one |
| **Fit to goal (double weight)** | Several of the properties the goal lists are simply not addressed | Only the easy properties are addressed | Every property is addressed but at least one only by accident of the implementation | All properties addressed, one of them fragile | Every property the goal lists has something in the code that deliberately answers it, and the choices left open are made in a way a reviewer would call sensible rather than arbitrary |

> Note (prereg S1-4): **Fit to goal** overlaps the hidden checks and is therefore
> correlated with the quantitative outcome. It must never be cited as independent
> qualitative corroboration.

## Worked examples for this task

**Readability** -- 1: one function with `d`, `s`, `r`, `tmp` and a while loop whose
exit condition needs tracing. 3: readable, but the tie-break between two jobs that
are both ready is an accident of dictionary order rather than a stated choice.
5: the tie-break is a named, commented decision, so the "same table gives the same
order" property is visible rather than incidental.

**Structure (double weight)** -- 1: the circle check, the ordering and the
collection of prerequisite-only jobs are one loop with three flags. 3: split, but
the set of all jobs is derived twice with slightly different rules. 5: one place
answers "what are all the jobs", one place answers "what is ready now", and the
circle is detected as the absence of anything ready rather than by a second
traversal.

**Error handling** -- 1: a circle makes it loop forever or blow the recursion
limit. 3: `ValueError` raised on a circle. 5: `ValueError("these jobs wait on each
other in a circle: build, test")` naming the jobs still stuck, which is what the
person reading the build log needs.

**Fit to goal (double weight)** -- 1: returns the keys in whatever order they were
in. 3: a correct order, but jobs that appear only as prerequisites are dropped.
5: all four properties deliberately answered, with the determinism coming from a
stated rule rather than from the input happening to be ordered.
