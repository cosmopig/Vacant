# e2e_trace — four real agents × planted-fault scenarios (L-fake)

started 2026-09-24T23:19:34+0000 · finished 2026-09-24T23:24:14+0000

| agent | scenario | attribution | got (state / class / grade) | step | feedback reached model | located in feedback | actor id in feedback | resolved | final | chain | hook p95 ms |
|---|---|---|---|---|---|---|---|---|---|---|---|
| claude | B_agent_fault | ✅ | located / agent / provable | 2 Bash | True | True | False | True | accept | True | 7.1 |
| claude | A_input_fault | ✅ | located / input / lineage_exact | None  | True | True | False | True | accept | True | 10.2 |
| claude | C_script_fault | ✅ | located / agent / lineage_internal | 1 Bash | True | True | False | True | accept | True | 11.0 |
| claude | D_unrecorded_change | ✅ | UNOBSERVED / unattributable / gap | None  | False | False | False | False | accept | True | 12.6 |
| claude | F_web_source_fault | ✅ | located / input / lineage_exact | None  | True | True | False | True | accept | True | 7.2 |
| claude | I_parallel_subagents | ✅ | located / agent / lineage_internal | 4 Bash | True | True | False | True | accept | True | 11.0 |
| claude | H_human_flag | ✅ | located / agent / heuristic | 2 Bash | True | True | False | True | accept | True | 9.8 |
| claude | G_background_subagent_fault | ✅ | located / agent / lineage_internal | 3 Bash | True | True | False | True | accept | True | 11.1 |
| claude | E_subagent_fault | ✅ | located / agent / lineage_internal | 2 Bash | True | True | False | True | accept | True | 7.2 |
| codex | B_agent_fault | ✅ | located / agent / provable | 2 Bash | True | True | False | True | accept | True | 9.4 |
| codex | A_input_fault | ✅ | located / input / lineage_exact | None  | True | True | False | True | accept | True | 11.0 |
| codex | C_script_fault | ✅ | located / agent / lineage_internal | 1 Bash | True | True | False | True | accept | True | 8.5 |
| codex | D_unrecorded_change | ✅ | UNOBSERVED / unattributable / gap | None  | False | False | False | False | accept | True | 6.7 |
| codex | F_web_source_fault | ✅ | located / input / lineage_exact | None  | True | True | False | True | accept | True | 8.7 |
| codex | I_parallel_subagents | ✅ | located / agent / lineage_internal | 6 Bash | True | True | False | True | accept | True | 9.6 |
| codex | H_human_flag | ✅ | located / agent / heuristic | 2 Bash | True | True | False | True | accept | True | 59.0 |
| codex | E_subagent_fault | ✅ | located / agent / lineage_internal | 3 Bash | True | True | False | True | accept | True | 6.8 |
| pi | B_agent_fault | ✅ | located / agent / provable | 2 write | True | True | False | True | accept | True | 7.7 |
| pi | A_input_fault | ✅ | located / input / lineage_exact | None  | True | True | False | True | accept | True | 7.3 |
| pi | C_script_fault | ✅ | located / agent / lineage_internal | 1 write | True | True | False | True | accept | True | 7.1 |
| pi | D_unrecorded_change | ✅ | UNOBSERVED / unattributable / gap | None  | False | False | False | False | accept | True | 7.1 |
| pi | F_web_source_fault | ✅ | located / input / lineage_exact | None  | True | True | False | True | accept | True | 7.0 |
| pi | I_parallel_subagents | ✅ | located / agent / lineage_internal | 3 write | True | True | False | True | accept | True | 7.0 |
| pi | H_human_flag | ✅ | located / agent / heuristic | 2 write | True | True | False | True | accept | True | 7.1 |
| pi | E_subagent_fault | ✅ | located / agent / lineage_internal | 2 write | True | True | False | True | accept | True | 7.3 |
| opencode | B_agent_fault | ✅ | located / agent / provable | 2 bash | False | False | False | False | reject | True | 7.2 |
| opencode | A_input_fault | ✅ | located / input / lineage_exact | None  | False | False | False | False | reject | True | 6.4 |
| opencode | C_script_fault | ✅ | located / agent / lineage_internal | 1 bash | False | False | False | False | reject | True | 9.3 |
| opencode | D_unrecorded_change | ✅ | UNOBSERVED / unattributable / gap | None  | False | False | False | False | accept | True | 6.8 |
| opencode | F_web_source_fault | ✅ | located / input / lineage_exact | None  | False | False | False | False | reject | True | 7.0 |
| opencode | I_parallel_subagents | ✅ | located / agent / lineage_internal | 3 bash | False | False | False | False | reject | True | 8.9 |
| opencode | H_human_flag | ✅ | located / agent / heuristic | 2 bash | False | False | False | False | accept | True | 6.9 |
| opencode | E_subagent_fault | ✅ | located / agent / lineage_internal | 2 bash | False | False | False | False | reject | True | 6.9 |

**attribution correct: 33/33**

- claude actors: {"cells": [["claude main [unknown]", 10, 10, 1]], "sources": {"input:inputs/summary.txt": 1, "url:http://portal.vacant-lab.test/web/q3.txt": 1}, "gaps": {"claude": 1}}
- codex actors: {"cells": [["codex main [claimed:mock-model]", 9, 9, 1]], "sources": {"input:inputs/summary.txt": 1, "url:http://portal.vacant-lab.test/web/q3.txt": 1}, "gaps": {"codex": 1}}
- pi actors: {"cells": [["pi main [claimed:mock/mock-model]", 9, 9, 1]], "sources": {"input:inputs/summary.txt": 1, "url:http://portal.vacant-lab.test/web/q3.txt": 1}, "gaps": {"pi": 1}}
- opencode actors: {"cells": [["opencode main [unknown]", 9, 3, 1]], "sources": {"input:inputs/summary.txt": 1, "url:http://portal.vacant-lab.test/web/q3.txt": 1}, "gaps": {"opencode": 1}}
