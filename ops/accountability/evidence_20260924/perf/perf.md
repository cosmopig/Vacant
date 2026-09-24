| files | hook without trace (ms) | first Pre (ms) | first full look | hooks while it runs, p50 (ms) | warm p50 (ms) | warm p95 (ms) | warm max (ms) | store growth per step (KB) | Stop: check＋trace (ms) | Stop feedback located the line | scanning turned off |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 100 | 132.2 | 206.4 | in hook | — | 141.1 | 218.1 | 218.1 | 12.1 | 180.4 | yes | no |
| 1000 | 153.2 | 522.0 | in hook | — | 150.2 | 180.5 | 180.5 | 0.9 | 230.7 | yes | no |
| 10000 | 136.1 | 2798.1 | in hook | — | 226.8 | 270.5 | 270.5 | 0.9 | 582.4 | yes | no |
| 40000 | 130.8 | 8194.2 | in hook | — | 542.9 | 603.5 | 603.5 | 0.9 | 1794.2 | yes | no |
| 60000 | 134.2 | 8321.5 | background | 140.5 | 131.7 | 218.9 | 218.9 | 0.0 | 1868.0 | no | workspace has more than 50000 files; narrow it (trace skips ['.cache', '.git', '.mypy_cache', '.pytest_cache', '.ruff_cache', '.tox', '.venv', '__pycache__', 'node_modules', 'venv']) |
