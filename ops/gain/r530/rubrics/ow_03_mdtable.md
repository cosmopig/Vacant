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

**Readability** -- 1: one `realign` of 150 lines with `i`, `j`, `k`, `f1`, `f2`
and a nest of index arithmetic. 3: splitting, width measuring and rendering are
separate but the pipe scanner is written twice with different escape handling.
5: `display_width`, `split_cells`, `render_table` read like their names, and the
only comment explains why the backslash and backtick states must be tracked in the
same scan.

**Structure** -- 1: fence tracking, table detection and padding interleaved in one
loop over lines. 3: table rendering split out but the separator row is special-cased
in three places. 5: cell splitting has one implementation that every caller shares,
so the escape rule cannot drift between detection and rendering.

**Error handling** -- this task's contract asks for no exceptions, so the dimension
reads as robustness. 1: an unclosed fence or a one-line table raises IndexError.
3: odd input does not crash but silently mangles a line. 5: every odd shape --
header with no body, ragged rows, a stray pipe in prose -- has a defined and
visible outcome in the code.

**Fit to goal** -- 1: `len(cell)` for width, so every CJK table is off by the number
of wide characters. 3: widths right, but tables inside fenced blocks are rewritten
too. 5: escaped pipes, inline code, fences, CRLF, ragged rows, empty cells and the
run-it-twice requirement each have something in the code that answers them.
