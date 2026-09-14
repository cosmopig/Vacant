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

**Readability** -- 1: one `compare` built from nested `try/int()` with `a1`, `a2`,
`p`, `q`. 3: parsing split out, but the pre-release rule is expressed as a chain of
`if` inside the comparison loop. 5: `parse_version` returns a named shape, an
`identifier_key` function says how one identifier sorts, and the one comment
explains why an all-digit identifier sorts below a textual one.

**Structure** -- 1: `satisfies` re-implements the comparison instead of calling
`compare`. 3: `satisfies` calls `compare` but the operator table is an if-chain
repeated for each operator. 5: one mapping from operator to accepted comparison
results, so adding an operator is one entry.

**Error handling** -- 1: a malformed version quietly compares as `(0, 0, 0)`.
3: `ValueError` raised, message generic. 5: `ValueError("not a version:
'1.2.x'")`, raised from the same place for both entry points, so a bad string
never reaches the comparison.

**Fit to goal** -- 1: string comparison, so 1.10 sorts before 1.9. 3: numbers
right and pre-release counted as older, but rc.10 sorts before rc.2. 5: numeric
identifiers by value, textual by ASCII, digits below text, longer pre-release
newer, commas and spaces in specs, and rejection rather than a guess.
