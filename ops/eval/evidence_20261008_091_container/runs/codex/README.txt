Codex 0.161.0, L-fake (scripted mock model, /home/user/Vacant/ops/intake/mock_model.py), docker --network none, fresh HOME=/home/u per container.
Dirs: <build>_<scenario>_<mode>; mode p = codex exec --json, ph = codex exec (plain), tui = tmux TUI. build none = no Vacant baseline.
Deviation: codex -s danger-full-access (bwrap cannot create namespaces inside the default docker profile; weakening seccomp was refused). The container is the sandbox.
Each dir: mock.jsonl (request log), bodies/ (raw requests), events.jsonl (hook events), frames*.txt/final_screen.txt (TUI), delivery.md, codex_stdout.jsonl/codex_stderr.txt, meta.json.
