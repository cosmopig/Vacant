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

**Readability** -- 1: a 120-line `convert()` with `a`, `b`, `tmp2`.
3: a parser and a serialiser, both followable, with the quote state machine
needing a second read. 5: `parse_records` / `records_to_objects` / `main`, and the
one comment in the file explains *why* the quote state has to be tracked across
line breaks rather than restating the loop.

**Structure** -- 1: parsing, validation and JSON writing interleaved in one loop
with three flags. 3: parsing split out but the header-duplicate rule is applied in
two places. 5: parsing returns records plus their starting line numbers, and every
caller of it gets line numbers for free.

**Error handling** -- 1: `except Exception: return ""`. 3: `ValueError("bad
input")` from both failure modes. 5: `line 4: expected 3 fields, got 2` and
`line 2: unclosed quote`, with the CLI turning exactly those into exit code 2.

**Fit to goal** -- 1: `text.split(",")`, so quoted commas are silently wrong.
3: quoting handled, but a repeated header column silently keeps the first value.
5: quoted commas, embedded newlines, doubled quotes, blank fields, repeated header
names, CRLF and non-ASCII all have a visible answer in the code, and the CLI
separates success from failure by exit code alone.
