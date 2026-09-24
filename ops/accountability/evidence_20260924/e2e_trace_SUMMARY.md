# e2e_trace — four real agents × four planted faults (L-fake)

started 2026-09-24T17:42:13+0000 · finished 2026-09-24T17:44:19+0000

| agent | scenario | attribution | got (state / class / grade) | step | feedback reached model | located in feedback | actor id in feedback | resolved | final | chain | hook p95 ms |
|---|---|---|---|---|---|---|---|---|---|---|---|
| claude | B_agent_fault | ✅ | located / agent / provable | 2 Bash | True | True | False | True | accept | True | 8.6 |
| claude | A_input_fault | ✅ | located / input / lineage_exact | None  | True | True | False | True | accept | True | 7.0 |
| claude | C_script_fault | ✅ | located / agent / lineage_internal | 1 Bash | True | True | False | True | accept | True | 6.5 |
| claude | D_unrecorded_change | ✅ | UNOBSERVED / unattributable / gap | None  | False | False | False | False | accept | True | 10.7 |
| codex | B_agent_fault | ✅ | located / agent / provable | 2 Bash | True | True | False | True | accept | True | 8.2 |
| codex | A_input_fault | ✅ | located / input / lineage_exact | None  | True | True | False | True | accept | True | 7.1 |
| codex | C_script_fault | ✅ | located / agent / lineage_internal | 1 Bash | True | True | False | True | accept | True | 7.4 |
| codex | D_unrecorded_change | ✅ | UNOBSERVED / unattributable / gap | None  | False | False | False | False | accept | True | 6.7 |
| pi | B_agent_fault | ✅ | located / agent / provable | 2 write | True | True | False | True | accept | True | 6.5 |
| pi | A_input_fault | ✅ | located / input / lineage_exact | None  | True | True | False | True | accept | True | 5.7 |
| pi | C_script_fault | ✅ | located / agent / lineage_internal | 1 write | True | True | False | True | accept | True | 8.0 |
| pi | D_unrecorded_change | ✅ | UNOBSERVED / unattributable / gap | None  | False | False | False | False | accept | True | 5.6 |
| opencode | B_agent_fault | ✅ | located / agent / provable | 2 bash | False | False | False | False | reject | True | 6.3 |
| opencode | A_input_fault | ✅ | located / input / lineage_exact | None  | False | False | False | False | reject | True | 6.0 |
| opencode | C_script_fault | ✅ | located / agent / lineage_internal | 1 bash | False | False | False | False | reject | True | 6.8 |
| opencode | D_unrecorded_change | ✅ | UNOBSERVED / unattributable / gap | None  | False | False | False | False | accept | True | 8.5 |

**attribution correct: 16/16**

- claude actors: {"cells": [["claude main [unknown]", 4, 4, 1]], "sources": {"input:inputs/summary.txt": 1}, "gaps": {"claude": 1}}
- codex actors: {"cells": [["codex main [claimed:mock-model]", 4, 4, 1]], "sources": {"input:inputs/summary.txt": 1}, "gaps": {"codex": 1}}
- pi actors: {"cells": [["pi main [claimed:mock/mock-model]", 4, 4, 1]], "sources": {"input:inputs/summary.txt": 1}, "gaps": {"pi": 1}}
- opencode actors: {"cells": [["opencode main [unknown]", 4, 1, 1]], "sources": {"input:inputs/summary.txt": 1}, "gaps": {"opencode": 1}}
