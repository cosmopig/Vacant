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

**Readability** -- 1: three regexes inlined into one `re.sub` chain with no names
and no examples. 3: named patterns, but the reader cannot tell which example from
the goal each one came from. 5: each pattern is named after the thing it catches and
carries the goal's own example beside it, so a reviewer can check the pattern
against the sample without leaving the file.

**Structure (double weight)** -- 1: `redact` and `findings` are two independent
ideas of what a secret is, so they can disagree. 3: a shared list of patterns but
the replacement logic is duplicated per kind. 5: one table of (name, pattern, how to
replace) driven by both entry points, so adding a fourth kind of secret is one
entry and the two functions cannot drift apart.

**Error handling** -- 1: a line that is not a string crashes deep inside `re`.
3: odd input survives without a crash. 5: the goal asks for no exceptions, so full
marks here means every odd input -- an empty line, a line that is entirely a
secret, a line with a half-formed secret -- has a defined and visible outcome, and
nothing is turned into an error that the goal did not ask to be one.

**Fit to goal (double weight)** -- 1: only the first of the three kinds is handled.
3: all three handled, but the replacement eats the surrounding line. 5: all three
kinds, the surrounding text preserved deliberately, a second pass proven to be a
no-op by construction rather than by luck, repeats handled, and a count a dashboard
can trust.
