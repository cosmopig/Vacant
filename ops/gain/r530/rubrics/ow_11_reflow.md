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

**Readability** -- 1: one `reflow` of 150 lines with `w`, `c`, `ln`, `f` and the
bullet regex written inline three times. 3: wrapping split out but the "how wide
is this" question is answered with `len()` in some places and a helper in others.
5: `display_width`, `split_into_pieces`, `wrap` and `bullet_of` read like their
names; the one comment explains why a wide character is its own piece.

**Structure** -- 1: fence tracking, paragraph grouping and wrapping interleaved in
one pass with three flags. 3: grouping separated, but the bullet paragraph and the
plain paragraph are wrapped by two near-identical code paths. 5: one wrapper taking
a first-line prefix and a continuation prefix, so bullets are just different
prefixes.

**Error handling** -- this contract asks for one exception, so the dimension reads
as robustness too. 1: `width=0` loops forever or divides by zero. 3: `ValueError`
raised, message generic. 5: `ValueError("width must be positive, got 0")`, and the
odd shapes -- an empty paragraph, a bullet with no text, an unclosed fence -- all
have a defined outcome.

**Fit to goal** -- 1: `textwrap.fill`, so wide characters, bullets and fences are
all wrong at once. 3: widths and bullets right, but Chinese is treated as one
unbreakable word. 5: two-column characters, breaks between them with no space,
hanging bullet indents, untouched fences, preserved blank runs, and long
unbreakable pieces left to stick out.
