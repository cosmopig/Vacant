---
name: vacant
description: Use when the project has a task contract (.vacant/contract.json or vacant.contract.json), or the user mentions Vacant, acceptance checks, a deliverable, or releasing work. Explains how to read the contract and run `vacant check` before declaring the task done.
---

# Working in a project with a Vacant task contract

This project defines what counts as a finished deliverable in a **task contract**.
The contract is the file `.vacant/contract.json` (or `vacant.contract.json`) at the
project root. It lists:

- `deliverable.include` / `exclude` — which files make up the deliverable;
- `claims` — each requirement, the verifier that checks it, and whether it is required;
- `release.destination` — where an accepted deliverable is published (by a separate step).

## Before you say the task is finished

1. Read the contract so you know which files and requirements are checked.
2. Run the checks yourself:

   ```bash
   vacant check            # or: python3 -m vacant_network check
   ```

   It prints one line per claim: `PASS`, `FAIL`, `UNKNOWN` (cannot be decided yet, e.g.
   waiting for a human review) or `CONFLICT`. Exit code 0 means every required claim passed.
   `vacant check --json` prints the same thing as JSON.
3. If a required claim fails, fix the deliverable and run `vacant check` again.

## Reading the feedback at the end of a turn

When the project is traced, the feedback names **where** the problem is, not just which check
failed:

    - total: FAIL — report.md:3 says "999"
      expected 69 (column 'amount', 3 rows)
      this value first appeared at step 2 (Bash)

- `report.md:3 says "999"` — the file, line and value the check objects to.
- `expected …` — what the check recomputed from the pinned inputs.
- `this value first appeared at step N (…)` — the tool call in this workspace's history that
  wrote the value; look at what that step did.
- `the same value is in inputs/notes.txt line 2 (the given input)` — the value was copied from
  an input. If that input is wrong, say so in the answer instead of hiding the difference.
- `the task owner marked these places in the deliverable as wrong` — a person pointed at a
  place (`vacant flag`); fix it or explain why it stands.

## Things to know

- `vacant check` is a dry run: it records nothing and publishes nothing.
- Do not edit `.vacant/`, the files listed under the contract's `inputs`, or `~/.vacant/`.
  Those are the requirements and the evidence sources, not part of the deliverable.
  Changing them does not make a claim pass: pinned inputs are hash-checked, and a changed
  input makes the claim `UNKNOWN`.
- Publishing is not part of your task. An accepted deliverable is released with
  `vacant release` by whoever holds the release decision; the destination re-checks
  everything before it accepts a version.
- `vacant review`, `vacant approve`, `vacant release`, `vacant withdraw`, `vacant keys` and
  `vacant contract lock` belong to the task's owner, reviewers and approvers. The working
  session uses `vacant check` (and, if asked, `vacant submit`).
- If a claim is `UNKNOWN` because it needs a human review or independent evidence, say so in
  your final message instead of trying to make it pass.
