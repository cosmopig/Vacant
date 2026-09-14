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

**Readability** -- 1: one regex built by string concatenation with three levels of
`if` on single characters and no name for what is being built. 3: translation split
out, but the segment scanner and the class scanner are tangled in one loop with two
flags. 5: `segment_matcher`, `compile_pattern` and a matcher that reads as "walk
the segments"; the one comment explains why a double star has to be tried at every
length.

**Structure** -- 1: `select` re-implements matching so the two can disagree.
3: `select` calls `matches` but re-parses each pattern for every path. 5: patterns
are compiled once and both entry points use the compiled form, so a pattern is
validated in exactly one place.

**Error handling** -- 1: a malformed class becomes a regex that raises deep inside
`re`, or worse, silently matches nothing. 3: `ValueError` raised for bad patterns.
5: `ValueError("unclosed [ in 'src/[abc.py'")`, raised when the pattern is read, so
`select` reports it even for a pattern that would have matched nothing.

**Fit to goal** -- 1: `fnmatch`, so a star crosses directory levels. 3: stars and
classes right, but the double star needs at least one segment. 5: one-level stars,
zero-or-more double stars, classes with ranges and negation, whole-path matching,
literal metacharacters, exclamation-mark removal and re-adding, and file-order
output with no repeats.
