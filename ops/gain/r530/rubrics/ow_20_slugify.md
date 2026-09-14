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

**Readability** -- 1: one function with three chained `re.sub` calls, a `while`
loop and a variable called `n`. 3: the cleaning is a named function but the
collision handling is inlined and its rule is not stated anywhere. 5: `clean(title)`
and a named collision strategy, and the fallback for a title with nothing Latin in
it is commented with why that fallback and not an empty string.

**Structure (double weight)** -- 1: cleaning, deduplication and the fallback are one
loop with two dictionaries. 3: split, but "is this slug taken" is asked in two
places with different answers. 5: one place turns a title into a candidate, one
place resolves a clash, so the uniqueness property is guaranteed by structure rather
than by having thought of each case.

**Error handling** -- 1: a title of only punctuation produces an empty string and no
one notices. 3: the empty case is handled but by a value that can itself collide.
5: every degenerate title -- empty, punctuation only, non-Latin only, already a
slug, a duplicate of another -- has a defined and visible outcome, and none of them
is turned into an exception the goal did not ask for.

**Fit to goal (double weight)** -- 1: no deduplication, so two identical titles give
one URL. 3: all properties addressed, but determinism comes from luck because the
collision suffix is drawn from a counter that depends on dictionary iteration.
5: order, character set, hyphen rules, uniqueness, determinism, the untouched clean
slug and the non-Latin fallback each have something in the code that deliberately
answers them.
