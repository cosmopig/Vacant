# e2e_trace — four real agents × planted-fault scenarios (L-fake)

started 2026-09-24T20:38:22+0000 · finished 2026-09-24T20:41:34+0000

| agent | scenario | attribution | got (state / class / grade) | step | feedback reached model | located in feedback | actor id in feedback | resolved | final | chain | hook p95 ms |
|---|---|---|---|---|---|---|---|---|---|---|---|
| claude | B_agent_fault | ✅ | located / agent / provable | 2 Bash | True | True | False | True | accept | True | 10.9 |
| claude | A_input_fault | ✅ | located / input / lineage_exact | None  | True | True | False | True | accept | True | 9.5 |
| claude | C_script_fault | ✅ | located / agent / lineage_internal | 1 Bash | True | True | False | True | accept | True | 9.5 |
| claude | D_unrecorded_change | ✅ | UNOBSERVED / unattributable / gap | None  | False | False | False | False | accept | True | 9.6 |
| claude | F_web_source_fault | ✅ | located / input / lineage_exact | None  | True | True | False | True | accept | True | 8.4 |
| claude | E_subagent_fault | ✅ | located / agent / lineage_internal | 2 Bash | True | True | False | True | accept | True | 9.8 |
| codex | B_agent_fault | ✅ | located / agent / provable | 2 Bash | True | True | False | True | accept | True | 13.8 |
| codex | A_input_fault | ✅ | located / input / lineage_exact | None  | True | True | False | True | accept | True | 9.6 |
| codex | C_script_fault | ✅ | located / agent / lineage_internal | 1 Bash | True | True | False | True | accept | True | 9.9 |
| codex | D_unrecorded_change | ✅ | UNOBSERVED / unattributable / gap | None  | False | False | False | False | accept | True | 8.2 |
| codex | F_web_source_fault | ✅ | located / input / lineage_exact | None  | True | True | False | True | accept | True | 8.3 |
| codex | E_subagent_fault | ✅ | located / agent / lineage_internal | 3 Bash | True | True | False | True | accept | True | 10.4 |
| pi | B_agent_fault | ✅ | located / agent / provable | 2 write | True | True | False | True | accept | True | 8.9 |
| pi | A_input_fault | ✅ | located / input / lineage_exact | None  | True | True | False | True | accept | True | 9.7 |
| pi | C_script_fault | ✅ | located / agent / lineage_internal | 1 write | True | True | False | True | accept | True | 8.3 |
| pi | D_unrecorded_change | ✅ | UNOBSERVED / unattributable / gap | None  | False | False | False | False | accept | True | 7.5 |
| pi | F_web_source_fault | ✅ | located / input / lineage_exact | None  | True | True | False | True | accept | True | 7.9 |
| pi | E_subagent_fault | ✅ | located / agent / lineage_internal | 2 write | True | True | False | True | accept | True | 8.1 |
| opencode | B_agent_fault | ✅ | located / agent / provable | 2 bash | False | False | False | False | reject | True | 10.6 |
| opencode | A_input_fault | ✅ | located / input / lineage_exact | None  | False | False | False | False | reject | True | 10.5 |
| opencode | C_script_fault | ✅ | located / agent / lineage_internal | 1 bash | False | False | False | False | reject | True | 7.3 |
| opencode | D_unrecorded_change | ✅ | UNOBSERVED / unattributable / gap | None  | False | False | False | False | accept | True | 9.3 |
| opencode | F_web_source_fault | ✅ | located / input / lineage_exact | None  | False | False | False | False | reject | True | 8.7 |
| opencode | E_subagent_fault | ✅ | located / agent / lineage_internal | 2 bash | False | False | False | False | reject | True | 8.4 |

**attribution correct: 24/24**

- claude actors: {"cells": [["claude main [unknown]", 6, 6, 1]], "sources": {"input:inputs/summary.txt": 1, "url:http://127.0.0.1:49013/web/q3.txt": 1}, "gaps": {"claude": 1}}
- codex actors: {"cells": [["codex main [claimed:mock-model]", 6, 6, 1]], "sources": {"input:inputs/summary.txt": 1, "url:http://127.0.0.1:47037/web/q3.txt": 1}, "gaps": {"codex": 1}}
- pi actors: {"cells": [["pi main [claimed:mock/mock-model]", 6, 6, 1]], "sources": {"input:inputs/summary.txt": 1, "url:http://127.0.0.1:45949/web/q3.txt": 1}, "gaps": {"pi": 1}}
- opencode actors: {"cells": [["opencode main [unknown]", 6, 1, 1]], "sources": {"input:inputs/summary.txt": 1, "url:http://127.0.0.1:37775/web/q3.txt": 1}, "gaps": {"opencode": 1}}
