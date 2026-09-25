# e2e_trace — four real agents × planted-fault scenarios (L-fake)

started 2026-09-25T01:46:20+0000 · finished 2026-09-25T01:50:54+0000

| agent | scenario | attribution | got (state / class / grade) | step | feedback reached model | located in feedback | actor id in feedback | resolved | final | chain | hook p95 ms |
|---|---|---|---|---|---|---|---|---|---|---|---|
| claude | B_agent_fault | ✅ | located / agent / provable | 2 Bash | True | True | False | True | accept | True | 13.3 |
| claude | A_input_fault | ✅ | located / input / lineage_exact | None  | True | True | False | True | accept | True | 8.6 |
| claude | C_script_fault | ✅ | located / agent / lineage_internal | 1 Bash | True | True | False | True | accept | True | 7.9 |
| claude | D_unrecorded_change | ✅ | UNOBSERVED / unattributable / gap | None  | False | False | False | False | accept | True | 6.9 |
| claude | F_web_source_fault | ✅ | located / input / lineage_exact | None  | True | True | False | True | accept | True | 7.6 |
| claude | I_parallel_subagents | ✅ | located / agent / lineage_internal | 3 Bash | True | True | False | True | accept | True | 9.0 |
| claude | H_human_flag | ✅ | located / agent / heuristic | 2 Bash | True | True | False | True | accept | True | 11.3 |
| claude | G_background_subagent_fault | ✅ | located / agent / lineage_internal | 3 Bash | True | True | False | True | accept | True | 7.2 |
| claude | E_subagent_fault | ✅ | located / agent / lineage_internal | 2 Bash | True | True | False | True | accept | True | 8.7 |
| codex | B_agent_fault | ✅ | located / agent / provable | 2 Bash | True | True | False | True | accept | True | 7.8 |
| codex | A_input_fault | ✅ | located / input / lineage_exact | None  | True | True | False | True | accept | True | 7.8 |
| codex | C_script_fault | ✅ | located / agent / lineage_internal | 1 Bash | True | True | False | True | accept | True | 7.1 |
| codex | D_unrecorded_change | ✅ | UNOBSERVED / unattributable / gap | None  | False | False | False | False | accept | True | 6.9 |
| codex | F_web_source_fault | ✅ | located / input / lineage_exact | None  | True | True | False | True | accept | True | 8.1 |
| codex | I_parallel_subagents | ✅ | located / agent / lineage_internal | 6 Bash | True | True | False | True | accept | True | 7.7 |
| codex | H_human_flag | ✅ | located / agent / heuristic | 2 Bash | True | True | False | True | accept | True | 8.0 |
| codex | E_subagent_fault | ✅ | located / agent / lineage_internal | 3 Bash | True | True | False | True | accept | True | 7.5 |
| pi | B_agent_fault | ✅ | located / agent / provable | 2 write | True | True | False | True | accept | True | 7.8 |
| pi | A_input_fault | ✅ | located / input / lineage_exact | None  | True | True | False | True | accept | True | 6.7 |
| pi | C_script_fault | ✅ | located / agent / lineage_internal | 1 write | True | True | False | True | accept | True | 7.4 |
| pi | D_unrecorded_change | ✅ | UNOBSERVED / unattributable / gap | None  | False | False | False | False | accept | True | 6.9 |
| pi | F_web_source_fault | ✅ | located / input / lineage_exact | None  | True | True | False | True | accept | True | 6.9 |
| pi | I_parallel_subagents | ✅ | located / agent / lineage_internal | 4 write | True | True | False | True | accept | True | 7.2 |
| pi | H_human_flag | ✅ | located / agent / heuristic | 2 write | True | True | False | True | accept | True | 8.2 |
| pi | E_subagent_fault | ✅ | located / agent / lineage_internal | 2 write | True | True | False | True | accept | True | 6.9 |
| opencode | B_agent_fault | ✅ | located / agent / provable | 2 bash | False | False | False | False | reject | True | 6.7 |
| opencode | A_input_fault | ✅ | located / input / lineage_exact | None  | False | False | False | False | reject | True | 6.8 |
| opencode | C_script_fault | ✅ | located / agent / lineage_internal | 1 bash | False | False | False | False | reject | True | 8.5 |
| opencode | D_unrecorded_change | ✅ | UNOBSERVED / unattributable / gap | None  | False | False | False | False | accept | True | 6.3 |
| opencode | F_web_source_fault | ✅ | located / input / lineage_exact | None  | False | False | False | False | reject | True | 6.6 |
| opencode | I_parallel_subagents | ✅ | located / agent / lineage_internal | 4 bash | False | False | False | False | reject | True | 8.1 |
| opencode | H_human_flag | ✅ | located / agent / heuristic | 2 bash | False | False | False | False | accept | True | 6.7 |
| opencode | E_subagent_fault | ✅ | located / agent / lineage_internal | 2 bash | False | False | False | False | reject | True | 9.2 |

**attribution correct: 33/33**

- claude actors: {"cells": [["claude main [unknown]", 10, 10, 1]], "sources": {"input:inputs/summary.txt": 1, "url:http://portal.vacant-lab.test/web/q3.txt": 1}, "gaps": {"claude": 1}}
- codex actors: {"cells": [["codex main [claimed:mock-model]", 9, 9, 1]], "sources": {"input:inputs/summary.txt": 1, "url:http://portal.vacant-lab.test/web/q3.txt": 1}, "gaps": {"codex": 1}}
- pi actors: {"cells": [["pi main [claimed:mock/mock-model]", 9, 9, 1]], "sources": {"input:inputs/summary.txt": 1, "url:http://portal.vacant-lab.test/web/q3.txt": 1}, "gaps": {"pi": 1}}
- opencode actors: {"cells": [["opencode main [unknown]", 9, 3, 1]], "sources": {"input:inputs/summary.txt": 1, "url:http://portal.vacant-lab.test/web/q3.txt": 1}, "gaps": {"opencode": 1}}
