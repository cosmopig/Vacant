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

**Readability** -- 1: one function with three chained `re.sub` calls, a `while`
loop and a variable called `n`. 3: the cleaning is a named function but the
collision handling is inlined and its rule is not stated anywhere. 5: `clean(title)`
and a named collision strategy, and the fallback for a title with nothing Latin in
it is commented with why that fallback and not an empty string.

**Structure** -- 1: cleaning, deduplication and the fallback are one
loop with two dictionaries. 3: split, but "is this slug taken" is asked in two
places with different answers. 5: one place turns a title into a candidate, one
place resolves a clash, so the uniqueness property is guaranteed by structure rather
than by having thought of each case.

**Error handling** -- 1: a title of only punctuation produces an empty string and no
one notices. 3: the empty case is handled but by a value that can itself collide.
5: every degenerate title -- empty, punctuation only, non-Latin only, already a
slug, a duplicate of another -- has a defined and visible outcome, and none of them
is turned into an exception the goal did not ask for.

**Fit to goal** -- 1: no deduplication, so two identical titles give
one URL. 3: all properties addressed, but determinism comes from luck because the
collision suffix is drawn from a counter that depends on dictionary iteration.
5: order, character set, hyphen rules, uniqueness, determinism, the untouched clean
slug and the non-Latin fallback each have something in the code that deliberately
answers them.
