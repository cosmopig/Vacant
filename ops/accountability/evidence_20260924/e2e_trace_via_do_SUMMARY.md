# e2e_trace — four real agents × planted-fault scenarios (L-fake)

started 2026-09-25T01:50:54+0000 · finished 2026-09-25T02:09:02+0000

| agent | scenario | attribution | got (state / class / grade) | step | feedback reached model | located in feedback | actor id in feedback | resolved | final | chain | hook p95 ms |
|---|---|---|---|---|---|---|---|---|---|---|---|
| claude | B_agent_fault | ✅ | located / agent / provable | 2 Bash | True | True | False | True | accept | True | 7.7 |
| claude | A_input_fault | ✅ | located / input / lineage_exact | None  | True | True | False | True | accept | True | 6.8 |
| claude | C_script_fault | ✅ | located / agent / lineage_internal | 1 Bash | True | True | False | True | accept | True | 7.2 |
| claude | F_web_source_fault | ✅ | located / input / lineage_exact | None  | True | True | False | True | accept | True | 7.4 |
| claude | I_parallel_subagents | ✅ | located / agent / lineage_internal | 4 Bash | True | True | False | True | accept | True | 8.3 |
| claude | G_background_subagent_fault | ✅ | located / agent / lineage_internal | 3 Bash | True | True | False | True | accept | True | 6.5 |
| claude | E_subagent_fault | ✅ | located / agent / lineage_internal | 2 Bash | True | True | False | True | accept | True | 6.6 |
| codex | B_agent_fault | ✅ | located / agent / provable | 2 Bash | True | True | False | True | accept | True | 6.3 |
| codex | A_input_fault | ✅ | located / input / lineage_exact | None  | True | True | False | True | accept | True | 6.2 |
| codex | C_script_fault | ✅ | located / agent / lineage_internal | 1 Bash | True | True | False | True | accept | True | 7.4 |
| codex | F_web_source_fault | ✅ | located / input / lineage_exact | None  | True | True | False | True | accept | True | 6.5 |
| codex | I_parallel_subagents | ✅ | located / agent / lineage_internal | 6 Bash | True | True | False | True | accept | True | 7.4 |
| codex | E_subagent_fault | ✅ | located / agent / lineage_internal | 3 Bash | True | True | False | True | accept | True | 6.9 |
| pi | B_agent_fault | ✅ | located / agent / provable | 2 write | True | True | False | True | accept | True | 6.9 |
| pi | A_input_fault | ✅ | located / input / lineage_exact | None  | True | True | False | True | accept | True | 6.5 |
| pi | C_script_fault | ✅ | located / agent / lineage_internal | 1 write | True | True | False | True | accept | True | 7.2 |
| pi | F_web_source_fault | ✅ | located / input / lineage_exact | None  | True | True | False | True | accept | True | 6.7 |
| pi | I_parallel_subagents | ✅ | located / agent / lineage_internal | 3 write | True | True | False | True | accept | True | 7.0 |
| pi | E_subagent_fault | ✅ | located / agent / lineage_internal | 2 write | True | True | False | True | accept | True | 7.1 |
| opencode | B_agent_fault | ✅ | located / agent / provable | 2 bash | True | True | False | True | accept | True | 7.4 |
| opencode | A_input_fault | ✅ | located / input / lineage_exact | None  | True | True | False | True | accept | True | 6.7 |
| opencode | C_script_fault | ✅ | located / agent / lineage_internal | 1 bash | True | True | False | True | accept | True | 7.8 |
| opencode | F_web_source_fault | ✅ | located / input / lineage_exact | None  | True | True | False | True | accept | True | 6.8 |
| opencode | I_parallel_subagents | ✅ | located / agent / lineage_internal | 4 bash | True | True | False | True | accept | True | 6.7 |
| opencode | E_subagent_fault | ✅ | located / agent / lineage_internal | 2 bash | True | True | False | True | accept | True | 7.0 |

**attribution correct: 25/25**

- claude actors: {"cells": [["claude main [unknown]", 7, 7, 1]], "sources": {"input:inputs/summary.txt": 1, "url:http://portal.vacant-lab.test/web/q3.txt": 1}, "gaps": {}}
- codex actors: {"cells": [["codex main [claimed:mock-model]", 6, 6, 1]], "sources": {"input:inputs/summary.txt": 1, "url:http://portal.vacant-lab.test/web/q3.txt": 1}, "gaps": {}}
- pi actors: {"cells": [["pi main [claimed:mock/mock-model]", 6, 6, 1]], "sources": {"input:inputs/summary.txt": 1, "url:http://portal.vacant-lab.test/web/q3.txt": 1}, "gaps": {}}
- opencode actors: {"cells": [["opencode main [unknown]", 6, 6, 1]], "sources": {"input:inputs/summary.txt": 1, "url:http://portal.vacant-lab.test/web/q3.txt": 1}, "gaps": {}}
