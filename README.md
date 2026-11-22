# Task workspaces and pre-existing-test gates

Vacant requires Python >=3.11. Use **Python 3.11** for these legacy workspaces:
newer interpreters can break base behavior before any edit. At this kit root:

```bash
PYTHON="${PYTHON:-python3.11}"
"$PYTHON" -m venv .venv
. .venv/bin/activate
python -m pip install git+https://github.com/cosmopig/Vacant 'pytest>=7,<8' 'setuptools<81'
```

Clone only your assigned `sandbox-v3/INSTANCE` branch into `INSTANCE/` under
this kit root (`git clone --single-branch --depth 1 --branch ...`). Read
`prompts/INSTANCE.txt` at the kit root: it is exactly the problem statement.
The workspace is an independent history-free base snapshot. Install the
repository's own dependencies using this kit-root environment; no environment
is bundled with the workspace. Django additionally needs `pytest-django`.
The pytest range supports older repository hooks; setuptools supplies the
legacy distutils compatibility module on Python 3.12. Match any further
repository-specific dependency constraints before using its gate.
Do not install a released copy of the project in place of the workspace source.

Only the gated arm uses the selected pre-existing tests and feedback. They
reveal which existing tests must stay green; this is part of the intervention.
Other arms do not inspect gates. Newly added tests are excluded even when their
labels appear in the passing-test list. There are no newly introduced acceptance tests
or reference fixes here. Parser labels are mapped to base test modules; labels
that describe several inherited/parameterized cases select those same labels,
not all tests in the module. Missing selected labels fail closed.

From `INSTANCE/`, with a fresh receipts directory each time:

```bash
../.venv/bin/vacant run --workspace . --suite ../gates/INSTANCE \
  --run-dir ../receipts/INSTANCE-N --sandbox none --retry none -- true
```

Use at most three submissions (N=1,2,3). The runner invokes only selected test
labels through the kit-root venv's Python and pytest, with the repository's
own fixtures/conftest. It does not run all tests or apply a separate test patch.
