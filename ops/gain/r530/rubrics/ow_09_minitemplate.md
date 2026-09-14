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

**Readability** -- 1: one `render` built from nested `while` loops over indices
with `i`, `j`, `k` and string slicing everywhere. 3: a tokenizer exists but the
block handling is done by re-scanning the template inside the loop. 5: tokenize,
then walk the tokens; `lookup(path, data, current)` states the name resolution rule
once, and the one comment explains why the escape has to be handled in the same
scan as the opening brace.

**Structure** -- 1: `render` calls itself on substrings, so the escape rule is
applied twice to the same text. 3: tokenizing and rendering separated but the
placeholder syntax is parsed in both. 5: one tokenizer is the only thing that knows
the syntax; the renderer only knows token kinds.

**Error handling** -- 1: a missing key becomes an empty string, which is the exact
failure the goal names. 3: `KeyError` raised but with the last path segment rather
than the whole path. 5: `KeyError("user.address.city")` carrying the name as
written, and a distinct `ValueError` for each malformed-template case, each naming
what is wrong.

**Fit to goal** -- 1: `str.replace` per key, so nested paths and repeats do not
work at all. 3: placeholders and repeats work, but comments and the brace escape
are missing. 5: nested lookup, repeats with item and field access, outer names
inside a block, empty lists, comments, the escape, and every malformed shape
reported.
