# e2e_trace — four real agents × planted-fault scenarios (L-fake)

started 2026-09-24T22:10:04+0000 · finished 2026-09-24T22:14:09+0000

| agent | scenario | attribution | got (state / class / grade) | step | feedback reached model | located in feedback | actor id in feedback | resolved | final | chain | hook p95 ms |
|---|---|---|---|---|---|---|---|---|---|---|---|
| claude | B_agent_fault | ✅ | located / agent / provable | 2 Bash | True | True | False | True | accept | True | 8.6 |
| claude | A_input_fault | ✅ | located / input / lineage_exact | None  | True | True | False | True | accept | True | 11.3 |
| claude | C_script_fault | ✅ | located / agent / lineage_internal | 1 Bash | True | True | False | True | accept | True | 15.6 |
| claude | D_unrecorded_change | ✅ | UNOBSERVED / unattributable / gap | None  | False | False | False | False | accept | True | 9.1 |
| claude | F_web_source_fault | ✅ | located / input / lineage_exact | None  | True | True | False | True | accept | True | 8.0 |
| claude | H_human_flag | ✅ | located / agent / heuristic | 2 Bash | True | True | False | True | accept | True | 11.4 |
| claude | G_background_subagent_fault | ✅ | located / agent / lineage_internal | 4 Bash | True | True | False | True | accept | True | 8.4 |
| claude | E_subagent_fault | ✅ | located / agent / lineage_internal | 2 Bash | True | True | False | True | accept | True | 8.8 |
| codex | B_agent_fault | ✅ | located / agent / provable | 2 Bash | True | True | False | True | accept | True | 10.5 |
| codex | A_input_fault | ✅ | located / input / lineage_exact | None  | True | True | False | True | accept | True | 8.0 |
| codex | C_script_fault | ✅ | located / agent / lineage_internal | 1 Bash | True | True | False | True | accept | True | 9.1 |
| codex | D_unrecorded_change | ✅ | UNOBSERVED / unattributable / gap | None  | False | False | False | False | accept | True | 7.2 |
| codex | F_web_source_fault | ✅ | located / input / lineage_exact | None  | True | True | False | True | accept | True | 8.4 |
| codex | H_human_flag | ✅ | located / agent / heuristic | 2 Bash | True | True | False | True | accept | True | 11.2 |
| codex | E_subagent_fault | ✅ | located / agent / lineage_internal | 3 Bash | True | True | False | True | accept | True | 7.7 |
| pi | B_agent_fault | ✅ | located / agent / provable | 2 write | True | True | False | True | accept | True | 8.1 |
| pi | A_input_fault | ✅ | located / input / lineage_exact | None  | True | True | False | True | accept | True | 8.5 |
| pi | C_script_fault | ✅ | located / agent / lineage_internal | 1 write | True | True | False | True | accept | True | 7.9 |
| pi | D_unrecorded_change | ✅ | UNOBSERVED / unattributable / gap | None  | False | False | False | False | accept | True | 6.6 |
| pi | F_web_source_fault | ✅ | located / input / lineage_exact | None  | True | True | False | True | accept | True | 7.5 |
| pi | H_human_flag | ✅ | located / agent / heuristic | 2 write | True | True | False | True | accept | True | 8.7 |
| pi | E_subagent_fault | ✅ | located / agent / lineage_internal | 2 write | True | True | False | True | accept | True | 8.1 |
| opencode | B_agent_fault | ✅ | located / agent / provable | 2 bash | False | False | False | False | reject | True | 7.3 |
| opencode | A_input_fault | ✅ | located / input / lineage_exact | None  | False | False | False | False | reject | True | 6.7 |
| opencode | C_script_fault | ✅ | located / agent / lineage_internal | 1 bash | False | False | False | False | reject | True | 7.7 |
| opencode | D_unrecorded_change | ✅ | UNOBSERVED / unattributable / gap | None  | False | False | False | False | accept | True | 11.2 |
| opencode | F_web_source_fault | ✅ | located / input / lineage_exact | None  | False | False | False | False | reject | True | 6.5 |
| opencode | H_human_flag | ✅ | located / agent / heuristic | 2 bash | False | False | False | False | accept | True | 7.2 |
| opencode | E_subagent_fault | ✅ | located / agent / lineage_internal | 2 bash | False | False | False | False | reject | True | 6.9 |

**attribution correct: 29/29**

- claude actors: {"cells": [["claude main [unknown]", 9, 9, 1]], "sources": {"input:inputs/summary.txt": 1, "url:http://portal.vacant-lab.test/web/q3.txt": 1}, "gaps": {"claude": 1}}
- codex actors: {"cells": [["codex main [claimed:mock-model]", 8, 8, 1]], "sources": {"input:inputs/summary.txt": 1, "url:http://portal.vacant-lab.test/web/q3.txt": 1}, "gaps": {"codex": 1}}
- pi actors: {"cells": [["pi main [claimed:mock/mock-model]", 8, 8, 1]], "sources": {"input:inputs/summary.txt": 1, "url:http://portal.vacant-lab.test/web/q3.txt": 1}, "gaps": {"pi": 1}}
- opencode actors: {"cells": [["opencode main [unknown]", 8, 3, 1]], "sources": {"input:inputs/summary.txt": 1, "url:http://portal.vacant-lab.test/web/q3.txt": 1}, "gaps": {"opencode": 1}}
