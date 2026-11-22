# Local coding-agent sandbox — task bank and ruler

Step 1 supplies twelve synthetic, offline tasks, reference solution overlays,
an independent pytest scorer, and the pi 0.87.1 / Ollama qwen3:8b runtime.
No agent batch or with/without effect estimate is included yet.

```bash
bash ops/sandbox/runtime/setup.sh
python3 ops/sandbox/runtime/proxy.py --port 18080 --log ~/sandbox-rt/calls.jsonl
RUN_TAG=example bash ops/sandbox/runtime/setup.sh
PI_CODING_AGENT_DIR=~/sandbox-rt/pi-agent pi -p --provider ollama --model qwen3:8b 'your task'
.venv/bin/python ops/sandbox/score.py billing /path/to/workspace-or.tar
```

Setup needs internet, Ubuntu systemd and passwordless sudo. Node 24 is the
selected LTS major; pi is pinned, while Ollama and its model tag are not immutable.
Record their versions/digests with experiment results. Setup does not start another
proxy automatically or overwrite the user's default pi configuration. Render one
models template per run into an isolated agent directory for concurrent runs.
The tagged base URL is `/t/<run_tag>/v1`; untagged `/v1` requests log a null tag.
Do not expose this unauthenticated localhost proxy to the network.

Only copy a task's `repo/` into the agent workspace and send its `prompt`.
Never expose `hidden/` or `solution/` to the agent, its context, or feedback.
For installed Vacant, install its extension into the same PI_CODING_AGENT_DIR;
do not disable extensions in that arm. No setup command installs Vacant itself.

The scorer copies regular files only (1 MiB/file, 10 MiB total, 500 files),
ignores caches and symlinks, and accepts directory or tar workspaces. Oversized
individual files are ignored; total/count overflow returns an error. Tar paths
must be relative and cannot traverse upward. Archives must contain workspace
contents at their root. Tests are replaced with originals before independent
visible and hidden pytest runs. Each suite has a five-second timeout, isolated
Python, disabled third-party pytest plugins/conftest and a temporary HOME.
`tests_modified` compares all submitted visible-test files with the originals;
added tests are reported as modifications too, not automatically rejected.
`output_file_ok` is null for non-output tasks. Overall success requires both
suites and any output check to pass. `n_failed` includes pytest failures/errors;
timeouts count as one failure. Error strings distinguish incomplete scoring.

This is hermetic test configuration, **not a security boundary against malicious
Python**: candidate code executes under the scorer's OS account and can access
the VM/network. Use an isolated VM/container and OS controls for hostile code.
Synthetic tasks and two successful runtime smokes do not establish a Vacant gain.

## Paired runner (preregister before executing)

Read `PREREG.md`. The default full run is 12 tasks × 4 arms × 1 sample;
the billing-only example below is a wiring smoke, not the full experiment:

```bash
.venv/bin/python ops/sandbox/runtime/proxy.py --port 18081 --log ~/sandbox-rt/tagged-calls.jsonl
.venv/bin/python ops/sandbox/run.py --tasks billing --arms A C G --samples 1 --seed 42 --out ~/sandbox-runs/billing-smoke
.venv/bin/python ops/sandbox/analyze.py ~/sandbox-runs/billing-smoke
```

For the full run use `--tasks all --arms A A2 C G`. Repeating the exact runner
command skips completed result.json cells. A partial cell gets a fresh work
directory; old partial evidence is preserved but excluded from the new run tag.
Changing the configuration under an existing output directory is refused.
All outputs must be outside this repository. `--agent-cmd` is a JSON argv
override for offline scripted tests only; it labels results L-fake.

The runner includes no global extension disable flag. Only C installs Vacant,
via the user's `vacant install --agents pi` command under that cell's HOME.
G's pytest adapter embeds original visible tests inside vrun's main() protocol;
bare pytest files would not be recognized by that gate. G uses `--sandbox none`
explicitly: trusted VM, not network/filesystem isolation. Its model still goes
directly through the tagged accounting proxy because pi uses models.json rather
than base-URL environment variables. G's `gate_requests_seen` may therefore be
zero: this arm tests the real executable acceptance/revise loop, **not** model
channel mediation. Visible-gate retries never contain hidden-test information.

The cell result distinguishes raw score from primary intention-to-treat outcome
(infra_void means primary failure). Analysis keeps infra cells in denominators
and lists missing scheduled cells. Costs without accounting rows are UNKNOWN.
Final-message success detection is deliberately a heuristic; inspect raw text.

## Batch2 results

The completed preregistered run (96/96 cells, 24 paired units) is archived in
[`results/batch2/`](results/batch2/), including the summary, runtime metadata and
progress records, but not cell workspaces. Hidden passes were A 8/24, A2 7/24,
C 8/24 and G 9/24, with infra-void cells retained in the denominators.
C−A Δ=0, p=1; G−A Δ=+0.042, p=1; the absolute A/A2 noise floor was 0.042.
Both comparisons show **no measurable gain** under `PREREG.md`.

G input/output token totals are **UNKNOWN**: `csv_export-s1-G` has proxy call
rows with empty usage after a timeout and a broken pipe, so the all-calls-usage
requirement makes its token counts, and therefore G's totals, UNKNOWN.
