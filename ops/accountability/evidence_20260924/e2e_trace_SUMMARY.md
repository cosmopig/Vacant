# e2e_trace — four real agents × five planted-fault scenarios (L-fake)

started 2026-09-24T20:30:07+0000 · finished 2026-09-24T20:32:50+0000

| agent | scenario | attribution | got (state / class / grade) | step | feedback reached model | located in feedback | actor id in feedback | resolved | final | chain | hook p95 ms |
|---|---|---|---|---|---|---|---|---|---|---|---|
| claude | B_agent_fault | ✅ | located / agent / provable | 2 Bash | True | True | False | True | accept | True | 8.6 |
| claude | A_input_fault | ✅ | located / input / lineage_exact | None  | True | True | False | True | accept | True | 9.3 |
| claude | C_script_fault | ✅ | located / agent / lineage_internal | 1 Bash | True | True | False | True | accept | True | 11.6 |
| claude | D_unrecorded_change | ✅ | UNOBSERVED / unattributable / gap | None  | False | False | False | False | accept | True | 10.1 |
| claude | E_subagent_fault | ✅ | located / agent / lineage_internal | 2 Bash | True | True | False | True | accept | True | 7.1 |
| codex | B_agent_fault | ✅ | located / agent / provable | 2 Bash | True | True | False | True | accept | True | 9.2 |
| codex | A_input_fault | ✅ | located / input / lineage_exact | None  | True | True | False | True | accept | True | 7.1 |
| codex | C_script_fault | ✅ | located / agent / lineage_internal | 1 Bash | True | True | False | True | accept | True | 10.5 |
| codex | D_unrecorded_change | ✅ | UNOBSERVED / unattributable / gap | None  | False | False | False | False | accept | True | 6.7 |
| codex | E_subagent_fault | ✅ | located / agent / lineage_internal | 3 Bash | True | True | False | True | accept | True | 7.6 |
| pi | B_agent_fault | ✅ | located / agent / provable | 2 write | True | True | False | True | accept | True | 10.6 |
| pi | A_input_fault | ✅ | located / input / lineage_exact | None  | True | True | False | True | accept | True | 6.9 |
| pi | C_script_fault | ✅ | located / agent / lineage_internal | 1 write | True | True | False | True | accept | True | 7.9 |
| pi | D_unrecorded_change | ✅ | UNOBSERVED / unattributable / gap | None  | False | False | False | False | accept | True | 7.1 |
| pi | E_subagent_fault | ✅ | located / agent / lineage_internal | 2 write | True | True | False | True | accept | True | 8.6 |
| opencode | B_agent_fault | ✅ | located / agent / provable | 2 bash | False | False | False | False | reject | True | 6.9 |
| opencode | A_input_fault | ✅ | located / input / lineage_exact | None  | False | False | False | False | reject | True | 7.6 |
| opencode | C_script_fault | ✅ | located / agent / lineage_internal | 1 bash | False | False | False | False | reject | True | 6.9 |
| opencode | D_unrecorded_change | ✅ | UNOBSERVED / unattributable / gap | None  | False | False | False | False | accept | True | 7.8 |
| opencode | E_subagent_fault | ✅ | located / agent / lineage_internal | 2 bash | False | False | False | False | reject | True | 6.7 |

**attribution correct: 20/20**

- claude actors: {"cells": [["claude main [unknown]", 5, 5, 1]], "sources": {"input:inputs/summary.txt": 1}, "gaps": {"claude": 1}}
- codex actors: {"cells": [["codex main [claimed:mock-model]", 5, 5, 1]], "sources": {"input:inputs/summary.txt": 1}, "gaps": {"codex": 1}}
- pi actors: {"cells": [["pi main [claimed:mock/mock-model]", 5, 5, 1]], "sources": {"input:inputs/summary.txt": 1}, "gaps": {"pi": 1}}
- opencode actors: {"cells": [["opencode main [unknown]", 5, 1, 1]], "sources": {"input:inputs/summary.txt": 1}, "gaps": {"opencode": 1}}
