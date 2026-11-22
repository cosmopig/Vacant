# Frozen v2 visible task kit

Twelve independent task workspaces, exact user prompts in `prompts/<task>.txt`
at the kit root, and full original visible-only acceptance trees embedded in
`gates/<task>/`. There are no hidden tests or reference solutions here. Work only
inside the assigned task directory; hand back its contents at the branch tree
root, not the entire kit. Use the visible gate only for the manual-gate arm.

## Gate environment (run at kit root)

Requires Python 3.11 or newer. The default below is Python 3.12; set `PYTHON`
to the full path of a suitable interpreter if it is not on PATH. Do not use a
system Python older than 3.11.

```bash
PYTHON="${PYTHON:-python3.12}"
"$PYTHON" -m venv .venv
. .venv/bin/activate
python -m pip install git+https://github.com/cosmopig/Vacant pytest
```

The wrappers locate this `.venv/bin/python` through workspace ancestors because
Vacant's verifier uses system Python and checks a frozen workspace under
`receipts/`. pytest is a separate prerequisite. `.venv/` and `receipts/` are
gitignored and must not be delivered inside a task workspace.

## Manual visible submission

From the assigned `<task>/` directory, substitute the task ID and a fresh N=1..3:

```bash
vacant run --workspace . --suite ../gates/<task> \
  --run-dir ../receipts/<task>-N --sandbox none --retry none -- true
```

An exit 20 refuses the submitted version; exit 0 accepts its visible checks.
Read feedback and repair manually, at most three submissions. This is not an
automatic Devin retry or a guarantee of correctness on independent scoring.
Keep receipts and raw gate outputs outside the delivered task workspace.
