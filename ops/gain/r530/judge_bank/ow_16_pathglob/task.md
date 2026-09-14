# Goal

A client has a build tool that picks files out of a list by pattern, the way a
build config or an ignore file does. They write the patterns by hand; the list of
files comes from a walk of the tree, so it is already in a sensible order.

A star should stay inside one directory level, because `src/*.py` is meant to be
the files in `src` and not everything underneath it. When they do want everything
underneath they write a double star, and that has to work even when there is
nothing underneath at all.

They also need a single-character wildcard and a way to say "one of these
characters" or "any character in this range", including the negative form.

A pattern has to match the whole path: half a match is not a match. Characters that
mean something to a regular expression -- a dot, a plus, a bracket sitting in a
file name -- are ordinary characters in a path.

They apply several patterns in order and want to take things back out again, so a
pattern beginning with an exclamation mark removes what the earlier ones picked up,
and a later pattern can put something back. The answer comes back in the order the
files were listed, with nothing listed twice.

A pattern they typed wrongly should be reported rather than quietly matching
nothing.

# Contract

    solution.matches(pattern: str, path: str) -> bool
    solution.select(patterns: list[str], paths: list[str]) -> list[str]

- Patterns and paths are split into segments on `/`. A pattern matches only when it
  accounts for every segment of the path.
- Inside one segment:
  - `?` matches exactly one character other than `/`;
  - `*` matches zero or more characters other than `/`;
  - `[abc]` matches one of the characters listed; `[a-z]` matches one character in
    that range; a leading `!` inside the brackets means "any one character that is
    not listed"; the class ends at the first `]`;
  - every other character stands for itself, whatever it would mean to a regular
    expression.
- A segment that is exactly `**` matches zero or more whole segments. A `**`
  appearing inside a larger segment is just two stars and has no extra meaning.
- `select` reads the patterns left to right. A plain pattern adds every path that
  matches it; a pattern beginning with `!` removes every path picked up so far that
  matches the rest of the pattern. The result is in the order of `paths` and holds
  no path twice.
- A pattern containing an unclosed `[`, or an empty class, raises `ValueError`.
  `select` checks every pattern it is given, whether or not anything matches it.
