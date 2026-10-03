# e2e_tui — four real agents' interactive TUIs × planted faults (L-fake)

started 2026-09-25T01:40:56+0000 · finished 2026-09-25T01:46:20+0000

| agent | scenario | attribution | got (state / class / grade) | feedback reached model (in the last turn) | shown to the person | actor id in feedback | resolved | final | person's prompts in trace (not typed by the person) | prompt resent | chain | earlier turns used the whole budget |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| claude | B_agent_fault | ✅ | located / agent / provable | True (True) | True | False | True | accept | 1 (0) | False | True | — |
| claude | A_input_fault | ✅ | located / input / lineage_exact | True (True) | True | False | True | accept | 1 (0) | False | True | — |
| claude | C_script_fault | ✅ | located / agent / lineage_internal | True (True) | True | False | True | accept | 1 (0) | False | True | — |
| claude | M_multi_turn | ✅ | located / agent / provable | True (True) | True | False | True | accept | 2 (0) | False | True | True |
| codex | B_agent_fault | ✅ | located / agent / provable | True (True) | True | False | True | accept | 1 (0) | False | True | — |
| codex | A_input_fault | ✅ | located / input / lineage_exact | True (True) | True | False | True | accept | 1 (0) | False | True | — |
| codex | C_script_fault | ✅ | located / agent / lineage_internal | True (True) | True | False | True | accept | 1 (0) | False | True | — |
| codex | M_multi_turn | ✅ | located / agent / provable | True (True) | True | False | True | accept | 2 (0) | False | True | True |
| pi | B_agent_fault | ✅ | located / agent / provable | True (True) | True | False | True | accept | 1 (0) | False | True | — |
| pi | A_input_fault | ✅ | located / input / lineage_exact | True (True) | True | False | True | accept | 1 (0) | False | True | — |
| pi | C_script_fault | ✅ | located / agent / lineage_internal | True (True) | True | False | True | accept | 1 (0) | False | True | — |
| pi | M_multi_turn | ✅ | located / agent / provable | True (True) | True | False | True | accept | 2 (0) | False | True | True |
| opencode | B_agent_fault | ✅ | located / agent / provable | True (True) | True | False | True | accept | 1 (0) | False | True | — |
| opencode | A_input_fault | ✅ | located / input / lineage_exact | True (True) | True | False | True | accept | 1 (0) | False | True | — |
| opencode | C_script_fault | ✅ | located / agent / lineage_internal | True (True) | True | False | True | accept | 1 (0) | False | True | — |
| opencode | M_multi_turn | ✅ | located / agent / provable | True (True) | True | False | True | accept | 2 (0) | False | True | True |

**attribution correct: 16/16** · feedback reached the model in the turn that wrote the error: 16/16 · shown to the person: 16/16 · accepted after the fix: 16/16 · model requests with a credential other than the fake key: 0 · multi-turn rows whose earlier turns used the whole budget (so the last turn's feedback can only come from the per-request reset): 4/4

