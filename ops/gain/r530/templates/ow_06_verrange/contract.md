# Contract

    solution.compare(a: str, b: str) -> int        # -1, 0 or 1
    solution.satisfies(version: str, spec: str) -> bool

- A version is `MAJOR.MINOR.PATCH`, each a run of digits, optionally followed by
  `-` and a pre-release made of dot-separated identifiers drawn from letters,
  digits and hyphens. Nothing else is a version.
- `compare(a, b)` returns `-1` when `a` is older, `0` when they are the same
  version and `1` when `a` is newer. It returns exactly those three values.
- The three numbers are compared as numbers, most significant first.
- A version carrying a pre-release is older than the same version without one.
- Two pre-releases are compared identifier by identifier: an identifier made only
  of digits is compared by value, any other identifier is compared by ASCII, and
  an all-digit identifier is older than one that is not. If every shared
  identifier is equal, the pre-release with more identifiers is the newer one.
- A spec is one or more conditions separated by `,`. Surrounding whitespace on a
  condition is not part of it. Every condition has to hold for `satisfies` to
  return True.
- A condition is one of `>=`, `>`, `<=`, `<`, `==`, `!=` followed by a version.
- A version that does not fit the shape above, a spec with an empty condition, and
  a condition with an unrecognised operator all raise `ValueError`.
