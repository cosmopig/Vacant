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

**Readability** -- 1: three regexes inlined into one `re.sub` chain with no names
and no examples. 3: named patterns, but the reader cannot tell which example from
the goal each one came from. 5: each pattern is named after the thing it catches and
carries the goal's own example beside it, so a reviewer can check the pattern
against the sample without leaving the file.

**Structure** -- 1: `redact` and `findings` are two independent
ideas of what a secret is, so they can disagree. 3: a shared list of patterns but
the replacement logic is duplicated per kind. 5: one table of (name, pattern, how to
replace) driven by both entry points, so adding a fourth kind of secret is one
entry and the two functions cannot drift apart.

**Error handling** -- 1: a line that is not a string crashes deep inside `re`.
3: odd input survives without a crash. 5: the goal asks for no exceptions, so full
marks here means every odd input -- an empty line, a line that is entirely a
secret, a line with a half-formed secret -- has a defined and visible outcome, and
nothing is turned into an error that the goal did not ask to be one.

**Fit to goal** -- 1: only the first of the three kinds is handled.
3: all three handled, but the replacement eats the surrounding line. 5: all three
kinds, the surrounding text preserved deliberately, a second pass proven to be a
no-op by construction rather than by luck, repeats handled, and a count a dashboard
can trust.
