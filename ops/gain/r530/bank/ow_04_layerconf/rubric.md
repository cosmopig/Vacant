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

**Readability** -- 1: one `load` of 100 lines with `d`, `f`, `e`, `x` and three
levels of nesting. 3: file parsing and environment parsing are separate functions
but the conversion rules are inlined in both. 5: `parse_file`, `env_key`, `coerce`
say what they do; the one comment explains why `bool` has to be tested before
`int`.

**Structure** -- 1: precedence expressed as an if-chain repeated per key.
3: layers applied in order but the conversion is written once for the file and
once for the environment. 5: one function applies "a layer of raw strings" and the
three layers are three calls to it, so adding a fourth source is one line.

**Error handling** -- 1: `int(value)` left to raise its own message, or worse, a
`try/except: pass` that turns a bad port into the default. 3: `ValueError` raised
for bad conversions with a generic message. 5: `ValueError("db.port: cannot read
'eighty' as an integer")`, and `KeyError` for an unknown key, so the caller learns
which setting and which value are at fault.

**Fit to goal** -- 1: returns a merged dict with no way to ask where a value came
from. 3: precedence and provenance right, but a typo'd key in the file silently
becomes a new setting. 5: sections, comments, missing file, values containing an
equals sign, unrelated environment variables, typo'd keys and unconvertible values
all have a visible answer.
