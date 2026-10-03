| files | hook without trace (ms) | first Pre (ms) | first full look | hooks while it runs, p50 (ms) | warm p50 (ms) | warm p95 (ms) | warm max (ms) | store growth per step (KB) | Stop: check＋trace (ms) | Stop feedback located the line | scanning turned off |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 100 | 132.6 | 167.4 | in hook | — | 136.2 | 165.5 | 165.5 | 12.1 | 174.6 | yes | no |
| 1000 | 141.2 | 288.3 | in hook | — | 143.6 | 193.8 | 193.8 | 0.9 | 257.8 | yes | no |
| 10000 | 133.6 | 3087.4 | in hook | — | 229.5 | 325.1 | 325.1 | 0.9 | 563.1 | yes | no |
| 40000 | 136.1 | 5737.4 | in hook | — | 557.3 | 597.3 | 597.3 | 0.9 | 1853.9 | yes | no |
| 60000 | 127.6 | 8309.6 | background | 129.7 | 134.5 | 227.1 | 227.1 | 0.0 | 2093.3 | no | workspace has more than 50000 files; narrow it (trace skips ['.cache', '.git', '.mypy_cache', '.pytest_cache', '.ruff_cache', '.tox', '.venv', '__pycache__', 'node_modules', 'venv']) |
