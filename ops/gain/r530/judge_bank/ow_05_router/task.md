# Goal

A client is writing a very small web framework and needs to take an incoming path
and find which registered pattern it belongs to, pulling out the named pieces of
the path along the way. Their problem is that a path often matches more than one
pattern, and they want the same answer every time -- the more specific one.

The routes are registered by half a dozen modules that load in whatever order the
importer happens to choose, so the answer must not depend on that order.

They also want a pattern that swallows the rest of the path for serving files,
and they want a mistake in a pattern to be reported when the route is registered
rather than on the first request that hits it.

A path that belongs to nobody has to be distinguishable from a path that matched
with no named pieces.

# Contract

    solution.Router()
    .add(pattern: str, name: str) -> None
    .match(path: str) -> tuple[str, dict[str, str]] | None

- A pattern begins with `/` and is read as segments split on `/`. A segment is
  one of three things: a literal, `{name}`, or `{name:*}`.
- `{name}` matches exactly one segment, never spans a `/`, and never matches an
  empty segment.
- `{name:*}` matches the whole remainder of the path, may contain `/`, must not be
  empty, and may only appear as the last segment.
- `match` returns the name of the winning pattern together with a dict mapping
  each parameter name to the text it captured, or `None` when nothing matches. A
  pattern with no parameters returns an empty dict.
- When more than one pattern matches, specificity decides. Rank the segments
  literal, then `{name}`, then `{name:*}`, and compare the two patterns segment by
  segment from the left: the first position at which they differ picks the winner.
  If neither differs anywhere they both reach, the pattern with more segments
  wins.
- Two patterns that differ only in their parameter names are the same pattern.
  Registering the second one raises `ValueError` from `add`.
- A pattern that does not begin with `/`, a segment holding an unmatched brace or
  an empty parameter name, and a `{name:*}` that is not last all raise
  `ValueError` from `add`.
- Paths handed to `match` always begin with `/`.
