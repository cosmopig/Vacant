# Contract

    solution.plan(jobs: dict[str, list[str]]) -> list[str]

- The keys of `jobs` are job names. Each value is the list of job names that have
  to finish before that job may start.
- `plan` returns a list of job names.
- When the goal cannot be satisfied, `plan` raises `ValueError`.

Nothing else is fixed here. The properties listed in the goal are what will be
checked; everything else is a design decision.
