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
