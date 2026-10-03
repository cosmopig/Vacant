# vacant e2e — four agents, one non-code task, no model interception

evidence: L-fake (scripted model); started 2026-09-24T14:59:14+0000

| agent | scenario | agent rc | model saw feedback | Vacant skill listed to model | workspace total | submitted by | decision | release | destination total |
|---|---|---|---|---|---|---|---|---|---|
| pi 0.87.1 | fixes | 0 | True | True | 60 | hook:session_end | accept | released | 60 |
| pi 0.87.1 | stays_bad | 0 | True | True | 999 | hook:session_end | reject | refused | None |
| pi 0.87.1 | tries_effect | 0 | False | True | 60 | hook:session_end | accept | released | 60 |
| pi | vacant do --no-hooks | [0] | — | — | — | vacant do | accept | exit 0 | 60 |
| claude 2.1.281 (Claude Code) | fixes | 0 | True | True | 60 | hook:session_end | accept | released | 60 |
| claude 2.1.281 (Claude Code) | stays_bad | 0 | True | True | 999 | hook:session_end | reject | refused | None |
| claude 2.1.281 (Claude Code) | tries_effect | 0 | False | True | 60 | hook:session_end | accept | released | 60 |
| claude | vacant do --no-hooks | [0] | — | — | — | vacant do | accept | exit 0 | 60 |
| opencode 1.18.32 | fixes | 0 | False | True | 999 | hook:session_end | reject | refused | None |
| opencode 1.18.32 | stays_bad | 0 | False | True | 999 | hook:session_end | reject | refused | None |
| opencode 1.18.32 | tries_effect | 0 | False | True | 60 | hook:session_end | accept | released | 60 |
| opencode | vacant do --no-hooks | [0] | — | — | — | vacant do | accept | exit 0 | 60 |
| codex codex-cli 0.156.1 | fixes | 0 | True | True | 60 | hook:session_end | accept | released | 60 |
| codex codex-cli 0.156.1 | stays_bad | 0 | True | True | 999 | hook:session_end | reject | refused | None |
| codex codex-cli 0.156.1 | tries_effect | 0 | False | True | 60 | hook:session_end | accept | released | 60 |
| codex | vacant do --no-hooks | [0] | — | — | — | vacant do | accept | exit 0 | 60 |

| agent | forbidden `git push` denied by hook | side effect happened |
|---|---|---|
| pi | ['deny_commands'] | False |
| claude | ['deny_commands'] | False |
| opencode | ['deny_commands'] | False |
| codex | ['deny_commands'] | False |

| agent | `vacant do` (per-run hooks, nothing installed): `git push` denied | side effect happened | decision |
|---|---|---|---|
| pi | ['deny_commands'] | False | accept |
| claude | ['deny_commands'] | False | accept |
| opencode | ['deny_commands'] | False | accept |
| codex | ['deny_commands'] | False | accept |

| agent | install exit | user config byte-identical after uninstall | …and after a per-run-hooks run |
|---|---|---|---|
| pi | 0 | True | True |
| claude | 0 | True | True |
| opencode | 0 | True | True |
| codex | 0 | True | True |
