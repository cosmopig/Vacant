# Goal

A client has a pile of jobs to run, one at a time, on a single worker. Some jobs
cannot start until other jobs have finished, and they keep that in a table from a
job name to the names of the jobs it waits for.

They want a planner that hands back an order to run them in. What they care about,
in their own words:

- nothing runs before something it waits for;
- every job appears in the order exactly once, and a job that is only ever
  mentioned as something else's prerequisite is still a job;
- running the planner twice on the same table gives the same order, because the
  order goes into a build log that they diff;
- a table that can never be run -- because some jobs wait on each other in a
  circle, directly or through others, or because a job waits on itself -- is
  reported as an error rather than returned half done.

Which of the many orders that satisfy those they get is up to whoever writes it.

# Contract

    solution.plan(jobs: dict[str, list[str]]) -> list[str]

- The keys of `jobs` are job names. Each value is the list of job names that have
  to finish before that job may start.
- `plan` returns a list of job names.
- When the goal cannot be satisfied, `plan` raises `ValueError`.

Nothing else is fixed here. The properties listed in the goal are what will be
checked; everything else is a design decision.
