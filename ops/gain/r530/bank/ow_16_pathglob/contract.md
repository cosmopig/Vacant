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
