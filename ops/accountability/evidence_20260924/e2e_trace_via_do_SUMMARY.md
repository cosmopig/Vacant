# e2e_trace — four real agents × planted-fault scenarios (L-fake)

started 2026-09-25T00:26:16+0000 · finished 2026-09-25T00:44:34+0000

| agent | scenario | attribution | got (state / class / grade) | step | feedback reached model | located in feedback | actor id in feedback | resolved | final | chain | hook p95 ms |
|---|---|---|---|---|---|---|---|---|---|---|---|
| claude | B_agent_fault | ✅ | located / agent / provable | 2 Bash | True | True | False | True | accept | True | 7.6 |
| claude | A_input_fault | ✅ | located / input / lineage_exact | None  | True | True | False | True | accept | True | 6.9 |
| claude | C_script_fault | ✅ | located / agent / lineage_internal | 1 Bash | True | True | False | True | accept | True | 7.7 |
| claude | F_web_source_fault | ✅ | located / input / lineage_exact | None  | True | True | False | True | accept | True | 6.8 |
| claude | I_parallel_subagents | ✅ | located / agent / lineage_internal | 4 Bash | True | True | False | True | accept | True | 8.5 |
| claude | G_background_subagent_fault | ✅ | located / agent / lineage_internal | 3 Bash | True | True | False | True | accept | True | 7.7 |
| claude | E_subagent_fault | ✅ | located / agent / lineage_internal | 2 Bash | True | True | False | True | accept | True | 8.2 |
| codex | B_agent_fault | ✅ | located / agent / provable | 2 Bash | True | True | False | True | accept | True | 7.7 |
| codex | A_input_fault | ✅ | located / input / lineage_exact | None  | True | True | False | True | accept | True | 7.1 |
| codex | C_script_fault | ✅ | located / agent / lineage_internal | 1 Bash | True | True | False | True | accept | True | 6.8 |
| codex | F_web_source_fault | ✅ | located / input / lineage_exact | None  | True | True | False | True | accept | True | 6.8 |
| codex | I_parallel_subagents | ✅ | located / agent / lineage_internal | 6 Bash | True | True | False | True | accept | True | 9.8 |
| codex | E_subagent_fault | ✅ | located / agent / lineage_internal | 3 Bash | True | True | False | True | accept | True | 6.7 |
| pi | B_agent_fault | ✅ | located / agent / provable | 2 write | True | True | False | True | accept | True | 6.3 |
| pi | A_input_fault | ✅ | located / input / lineage_exact | None  | True | True | False | True | accept | True | 6.8 |
| pi | C_script_fault | ✅ | located / agent / lineage_internal | 1 write | True | True | False | True | accept | True | 9.5 |
| pi | F_web_source_fault | ✅ | located / input / lineage_exact | None  | True | True | False | True | accept | True | 6.9 |
| pi | I_parallel_subagents | ✅ | located / agent / lineage_internal | 3 write | True | True | False | True | accept | True | 6.9 |
| pi | E_subagent_fault | ✅ | located / agent / lineage_internal | 2 write | True | True | False | True | accept | True | 6.6 |
| opencode | B_agent_fault | ✅ | located / agent / provable | 2 bash | True | True | False | True | accept | True | 6.9 |
| opencode | A_input_fault | ✅ | located / input / lineage_exact | None  | True | True | False | True | accept | True | 6.6 |
| opencode | C_script_fault | ✅ | located / agent / lineage_internal | 1 bash | True | True | False | True | accept | True | 7.5 |
| opencode | F_web_source_fault | ✅ | located / input / lineage_exact | None  | True | True | False | True | accept | True | 12.3 |
| opencode | I_parallel_subagents | ✅ | located / agent / lineage_internal | 4 bash | True | True | False | True | accept | True | 14.2 |
| opencode | E_subagent_fault | ✅ | located / agent / lineage_internal | 2 bash | True | True | False | True | accept | True | 11.2 |

**attribution correct: 25/25**

- claude actors: {"cells": [["claude main [unknown]", 7, 7, 1]], "sources": {"input:inputs/summary.txt": 1, "url:http://portal.vacant-lab.test/web/q3.txt": 1}, "gaps": {}}
- codex actors: {"cells": [["codex main [claimed:mock-model]", 6, 6, 1]], "sources": {"input:inputs/summary.txt": 1, "url:http://portal.vacant-lab.test/web/q3.txt": 1}, "gaps": {}}
- pi actors: {"cells": [["pi main [claimed:mock/mock-model]", 6, 6, 1]], "sources": {"input:inputs/summary.txt": 1, "url:http://portal.vacant-lab.test/web/q3.txt": 1}, "gaps": {}}
- opencode actors: {"cells": [["opencode main [unknown]", 6, 6, 1]], "sources": {"input:inputs/summary.txt": 1, "url:http://portal.vacant-lab.test/web/q3.txt": 1}, "gaps": {}}
