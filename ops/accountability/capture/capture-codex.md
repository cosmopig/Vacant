# Codex CLI 0.156.1: capturing the trajectory (who did what) for accountability

Lens: what a person running **one** Codex agent can hand to Vacant, so that Vacant can
(1) record who did what as it happens, (2) trace a failed check back to the step that caused it, and
(3) attribute that step to an actor (agent / sub-agent / model).

The earlier sheet `scratchpad/understand/agent-codex.md` covered pre-tool deny, Stop and session end.
This sheet covers **trajectory capture** only.

## Evidence and conventions

- **Binary:** `codex-cli 0.156.1`, the npm musl build at `scratchpad/agents/node_modules/.bin/codex`.
- **Source:** git tag `rust-v0.156.1` at `scratchpad/codex_probe/codex-src`. Paths in [SRC] tags are relative to `codex-rs/`.
- **Model backend:** every run used a scripted local mock of the Responses API, `accountability/codex/mock_traj.py`, derived from `ops/intake/mock_model.py`.
  - The isolated `CODEX_HOME` was `runs/<label>/home`, and the fake key was `MOCK_KEY=sk-fake-not-real`.
  - No real API was contacted and no real credential was read.
  - The model slug was usually `gpt-5.5`. Codex only uses the slug to look up metadata in its bundled catalog (`codex debug models`).
- **Hooks:** all 12 hook events were registered, trusted with hashes computed in `run_probe.py`, and logged by `hook_log.py`.
- **Driver files**, all under `accountability/codex/`:
  - `run_probe.py`: `codex exec` runs.
  - `appserver_capture.py`: `codex app-server` runs.
  - `otlp_sink.py`: a local OTLP receiver.
  - `mcp_docs.py`: a stdio MCP server that stands in for an external document or API.
  - `traceback_demo.py`: the join and trace-back proof.
- **Raw evidence** for each run is in `accountability/codex/runs/<label>/`:
  - `events.jsonl` (the `--json` stream), `hook_log.jsonl`, and `home/sessions/**/rollout-*.jsonl`;
  - `mock/req_NNN.json`, the full request body and headers minus `Authorization`;
  - `mock/mock_log.jsonl`, `stderr.txt` and `rc.txt`.

| label | what it exercises |
|---|---|
| S1_single | shell read, MCP fetch, hosted web_search, apply_patch add, a failing check command; then `exec resume` for a second turn |
| S2_subagent / S2b_bad_input | multi-agent v1: spawn → sub-agent reads and writes → wait → parent writes → close. S2: the sub-agent introduces the error. S2b: the input file is already wrong |
| S4_codemode | model `gpt-6-luna` (`tool_mode=code_mode_only`), with nested tools inside a JS `exec` cell |
| S5_failures / S11_sandbox_denied | failed apply_patch, sandbox-denied write, a long-running command, malformed arguments |
| S6_served_model | the server answers with a different model (`openai-model` response header) |
| S7_otel | the S2 scenario with the OTLP log and trace exporters pointed at a local sink |
| S8_appserver | the S2 scenario through `codex app-server`, capturing every JSON-RPC notification |
| S9_submodel_tamper | sub-agent on a different model (`gpt-6-luna`); the agent appends a forged line to its own rollout |
| S10_parallel | three tool calls in one model response |
| S12_cli_hooks_subagent | hooks injected **only** via `-c` (session flags): do they reach sub-agents? |
| S13_v2 | multi-agent **v2** (`gpt-6-luna` default: paths, `agent_message`, encrypted hand-off field) |

Tags: **[RUN]** means I executed it here and saw it; **[SRC]** means I read it in the source; **[INF]** is inference; **[DOC]** is official docs. Most facts below are [RUN].

---

## 0. Bottom line

1. **`PostToolUse` exists in 0.156.1 and carries the model's own call id. [RUN S1/S2/S4/S10]**
   - Payload: `session_id, turn_id, transcript_path, cwd, hook_event_name, model, permission_mode, tool_name, tool_input, tool_response, tool_use_id`.
   - Inside a sub-agent it also carries `agent_id, agent_type`.
   - `tool_use_id` equals the Responses `call_id`, the rollout `function_call.call_id`, the rollout `item_completed.item.id`, the app-server item `id` and the OTEL `call_id`. It is the universal join key.
   - Code mode is the exception (fact 7).
2. **The rollout JSONL is the only complete per-thread record** that exists without a proxy [RUN].
   - It includes `response_id` for each model response, `turn_context.model`, full apply_patch content and diffs, `exit_code`, shell read classification (`parsed_cmd`), and sub-agent parentage.
   - **Each sub-agent gets its own rollout file**, and its `session_meta` names the parent.
3. **`codex exec --json` is not enough for accountability. [RUN]** It is missing:
   - the sub-agent's own steps (S2: the faulty `printf … > figure.txt` is absent);
   - failed apply_patch and sandbox-denied commands (S5/S11);
   - `tool_search`, hook runs, `turn_id` and call ids.
   - Its item ids are synthetic: `item_N` [SRC exec/src/event_processor_with_jsonl_output.rs:101].
   - Under multi-agent v2 it omits the spawn entirely (S13).
4. **Hooks see sub-agents and code-mode nested tools; they do not see some hosted or meta steps. [RUN]**
   - Sub-agents: `SubagentStart`/`SubagentStop` fire, plus every Pre/PostToolUse inside the sub-agent with `agent_id`.
   - Code mode: nested tools appear with `tool_use_id="exec-<uuid>"`.
   - No hook fires for: hosted `web_search`, `tool_search`, the outer code-mode `exec` cell, malformed-argument calls, or reasoning.
   - PostToolUse is also absent when a tool handler fails: failed apply_patch, a still-running process.
5. **Hooks injected with `-c` reach sub-agents. [RUN S12]** Vacant can capture a whole multi-agent session without writing the user's `config.toml`.
6. **Responsibility for a model response is recoverable only positionally. [RUN]**
   - A hook payload's `turn_id` is the **user turn**, which spans many model responses. No hook payload carries `response_id`.
   - The rollout writes `token_usage_record{response_id,…}` **right after** the items of that response. So "items since the previous `token_usage_record`" equals "issued by this response".
7. **Code mode**, the default for the `gpt-6-*` / `gpt-5.6-*` catalog entries (`tool_mode=code_mode_only`), breaks the direct link between the model's call id and the real tool steps. [RUN S4/S9/S13]
   - The model's single `custom_tool_call{name:"exec", call_id}` is JavaScript.
   - The nested `tools.exec_command` / `tools.apply_patch` calls get hooks and rollout items with ids `exec-<uuid>`, and **no field links them to the cell's `call_id`**. They are linked only by position between `custom_tool_call` and its `custom_tool_call_output`.
   - Internally `ToolCallSource::CodeMode{cell_id, runtime_tool_call_id}` exists [SRC core/src/tools/context.rs:56-67] but it is not emitted.
8. **Model identity** [RUN]:
   - Hooks carry the **requested** slug per actor. A sub-agent spawned with `model:"gpt-6-luna"` shows `model:"gpt-6-luna"` in its hooks, wire body and `turn_context`.
   - The **served** model (response header `openai-model`) surfaces **only** as a one-time `--json` error item, `"model rerouted: gpt-5.5 -> gpt-served-snapshot-x (HighRiskCyberActivity)"`. It is not in the rollout and not in hooks (S6).
9. **The rollout is not tamper-evident. [RUN S9]**
   - With a sandbox-writable `CODEX_HOME` (anything under /tmp, or danger-full-access), the agent's own shell appended `{"type":"forged_by_agent",…}` to its rollout, and Codex kept writing after it.
   - The agent's shell sees `CODEX_HOME CODEX_SESSION_ID CODEX_THREAD_ID CODEX_SANDBOX_NETWORK_DISABLED …`.
   - ⇒ Vacant must sign and chain at hook time. Hooks run outside the sandbox: their env lacks `CODEX_SANDBOX_NETWORK_DISABLED`. Vacant should also seal the rollout hash at `Stop`/`SubagentStop`/`SessionEnd`.
10. **Shell writes are the biggest blind spot.** For `printf … > figure.txt`, every channel records only the command string [RUN]:
    - `tool_response:""`;
    - `parsed_cmd:[{"type":"unknown"}]`;
    - no path and no content.
    - apply_patch writes are fully recorded (content or `unified_diff`).
    - ⇒ Vacant needs its own file snapshots around tool calls. Concurrency makes that ambiguous (fact 12).
11. **Hosted `web_search` content is invisible** at the client [RUN S1]. Only `{query, action}` is recorded; the results never reach Codex.
12. **Tool calls run concurrently.** [RUN S10, S2]
    - Parallel calls from one response, and parent vs. sub-agent threads, overlap in time.
    - PostToolUse arrives in completion order.
    - "What changed between Pre and Post" is therefore not attributable to one call without per-call isolation.

---

## 1. Channel × fact matrix (what each channel can tell Vacant)

✅ = present, ◐ = partial or indirect, ❌ = absent. All cells are [RUN] unless marked otherwise.

| fact needed for accountability | hooks (Pre/PostToolUse etc.) | `exec --json` | rollout JSONL | app-server notifications | OTEL logs | wire (proxy / mock) |
|---|---|---|---|---|---|---|
| tool name + input | ✅ `tool_name`,`tool_input` (normalized) | ◐ per item type | ✅ raw `arguments`/`input` | ✅ | ✅ `tool_name`,`tool_namespace`,`arguments` | ✅ in the next request's `input` |
| tool output | ✅ `tool_response` (model-visible text; **no exit code** for Bash) | ✅ `aggregated_output`,`exit_code` | ✅ `stdout`,`stderr`,`exit_code` + `function_call_output` | ✅ | ◐ truncated `output` | ✅ |
| universal call id | ✅ `tool_use_id` | ❌ `item_N` | ✅ `call_id` / `item.id` | ✅ `item.id` | ✅ `call_id` | ✅ |
| which model **response** issued it | ❌ | ❌ | ◐ positional `token_usage_record.response_id` | ◐ | ❌ | ✅ (the response itself) |
| user turn | ✅ `turn_id` | ❌ | ✅ `turn_id`, `root_turn_id` | ✅ `turnId` | ❌ | ✅ `x-codex-turn-metadata.turn_id` |
| agent / sub-agent identity | ✅ `agent_id`,`agent_type` (absent ⇒ root) | ◐ only `collab_tool_call` in the parent | ✅ separate file; `session_meta.{id,parent_thread_id,agent_nickname,agent_path,source.subagent.thread_spawn.depth}` | ✅ `threadId` | ✅ `agent_name` (nickname or `/root`), `conversation.id` | ✅ `x-openai-subagent: collab_spawn`, `x-codex-parent-thread-id`, meta `thread_source`,`agent_name` |
| model per actor | ✅ `model` (requested slug) | ❌ | ✅ `turn_context.model`; `CollabAgentToolCall.model`,`reasoning_effort` | ✅ | ✅ `model` | ✅ body `model` + meta `model`,`reasoning_effort` |
| served model ≠ requested | ❌ | ◐ one error item | ❌ | [INF] warning notif | ❌ | ✅ response header `openai-model` |
| files written by apply_patch | ◐ patch text in `tool_input.command` | ◐ path + `kind` only | ✅ `FileChange.changes{path:{type:add,content}|{type:update,unified_diff,move_path}}` | ✅ `fileChange.changes[].diff` + `turn/diff/updated` | ◐ `arguments` | ✅ |
| files written by shell | ❌ (command string only) | ❌ | ❌ (`parsed_cmd` `unknown`) | ❌ | ❌ | ❌ |
| files read by shell | ◐ command string + output | ◐ | ✅ `parsed_cmd:[{type:"read",name,path}]` (heuristic parser) + content | ✅ `commandActions[{type:"read",path}]` | ❌ | ✅ |
| MCP (external source) | ✅ `mcp__<srv>__<tool>`, full `CallToolResult` incl. `_meta` | ✅ `mcp_tool_call` | ✅ `McpToolCall` (+`readOnlyHint`) | ✅ | ✅ `mcp_server` | ✅ |
| hosted web_search | ❌ | ◐ query only (duplicate `"id"` key!) | ◐ `web_search_call{action.query}` | ◐ | ❌ | ◐ query only |
| sub-agent hand-off text | ✅ `spawn_agent` `tool_input.message` (v1) | ✅ `prompt` (v1) / ❌ (v2) | ✅ (v1 `prompt`; v2 `agent_message{author,recipient}` NEW_TASK with an `encrypted_content` payload) | ✅ | ✅ | ✅ |
| sub-agent result back to parent | ✅ `SubagentStop.last_assistant_message`; `wait_agent` `tool_response` | ◐ `agents_states` (v1) | ✅ `wait` output + injected `<subagent_notification>` user msg (v1) / `agent_message` FINAL_ANSWER (v2) | ✅ | ✅ | ✅ |
| user prompt / requirement | ✅ `UserPromptSubmit.prompt` | ❌ | ✅ user `message` + `UserMessage` item; AGENTS.md / skills as developer or user messages | ✅ | ◐ `[REDACTED]` by default | ✅ |
| reasoning | ❌ | ✅ (if the server sends plaintext) | ✅ `reasoning{summary,content,encrypted_content}` | ✅ | ❌ | ✅ |

---

## 2. (a) Hooks: events, payloads and firing rules

**Registration used** [RUN]. Either a user `config.toml` with `[[hooks.<Event>]]` plus `[hooks.state."<file>:<snake_event>:0:0"] trusted_hash=…`, or pure `-c`:

```
-c 'hooks.PostToolUse=[{hooks=[{type="command",command="python3 …/hook_log.py PostToolUse",timeout=30}]}]'
-c 'hooks.state={"/<session-flags>/config.toml:post_tool_use:0:0"={trusted_hash="sha256:…",enabled=true}, …}'
--enable hooks
```

The hash formula is the one in agent-codex.md §3.3. It is reproduced in `run_probe.py:hook_hash`, and all 12 events ran trusted. With no `matcher`, a hook matches every tool.

### 2.1 Common fields [RUN]

- Every event carries `session_id`, `transcript_path`, `cwd` and `hook_event_name`.
- Every event except SessionEnd also carries `model` and `permission_mode` (`"bypassPermissions"` in exec). SessionEnd has neither.
- Turn-scoped events add `turn_id`.
- Events fired inside a sub-agent add `agent_id` (the sub-agent's thread id) and `agent_type` (`"default"` unless a role was given).
- `session_id` in a sub-agent is the **root** session id, not the sub-agent's thread.
- `transcript_path` inside a sub-agent is the **sub-agent's** rollout.

### 2.2 Per event (observed)

| event | extra fields | fires for sub-agent? | notes |
|---|---|---|---|
| SessionStart | `source`: `startup` or `resume` [RUN resume] | ❌ (SubagentStart instead) | |
| UserPromptSubmit | `prompt` | ✅ `prompt` = the spawn message (v1) | ⇒ the hand-off text is visible at the child too |
| PreToolUse | `tool_name, tool_input, tool_use_id` | ✅ | fires even when the tool then fails |
| PostToolUse | `+ tool_response` | ✅ | see §2.4 for when it does **not** fire |
| SubagentStart | `agent_id, agent_type`; `turn_id` = child's turn; `transcript_path` = child's rollout | — | **no** parent `tool_use_id`. Link via the parent's `PostToolUse(spawn_agent).tool_response.agent_id` (v1) or the rollout `SubAgentActivity` (v2) |
| SubagentStop | `agent_id, agent_type, agent_transcript_path` (child), `transcript_path` (parent), `last_assistant_message`, `stop_hook_active` | — | the sub-agent's self-reported result |
| Stop | `stop_hook_active, last_assistant_message` | ❌ | the root agent's claim of done |
| SessionEnd | `reason:"other"`; no `turn_id`, no `model` | ❌ | 1–3 s timeout |
| PermissionRequest, Pre/PostCompact, Interrupt | not triggered in these runs (exec forces approval `never`; no compaction or interrupt) | | schema in hooks/schema/generated/*.json [SRC] |

### 2.3 `tool_name` / `tool_input` / `tool_response` shapes [RUN]

| model call | `tool_name` | `tool_input` | `tool_response` |
|---|---|---|---|
| `exec_command{"cmd":…}` | `Bash` | `{"command":"cat notes.txt"}` | `"Varda is a river city.\nPopulation: 412,300 (2025).\n"` (a plain string: output only, **no exit code**; S1 `grep` exit 1 gave `"0\n"`) |
| apply_patch (custom/freeform) | `apply_patch` | `{"command":"*** Begin Patch\n*** Add File: brief.md\n+…"}` | `"Exit code: 0\nWall time: 0 seconds\nOutput:\nSuccess. Updated the following files:\nA brief.md\n"` |
| MCP `namespace:"mcp__docs", name:"fetch_doc"` | `mcp__docs__fetch_doc` | `{"name":"population_brief"}` | `{"content":[{"type":"text","text":"…412,300…"}],"isError":false,"_meta":{"sha256":"6f38…"}}` |
| v1 `multi_agent_v1/spawn_agent` | `spawn_agent` (special-cased [SRC core/src/tools/registry.rs:824-833]) | `{"message":"SUBTASK-A: …"}` | `"{\"agent_id\":\"01a0d451-e6f8-…\",\"nickname\":\"Hypatia\"}"` |
| v1 `wait_agent` / `close_agent` | **`multi_agent_v1wait_agent`**, **`multi_agent_v1close_agent`** (namespace glued on without a separator: `flat_tool_name`) | `{"targets":[…],"timeout_ms":30000}` | `"{\"status\":{\"<id>\":{\"completed\":\"Wrote 421,300 to figure.txt\"}},\"timed_out\":false}"` |
| v2 `collaboration/spawn_agent` | **`collaborationspawn_agent`** (not special-cased in v2) | `{"task_name":"figure_worker","message":…,"fork_turns":"none"}` | `"{\"task_name\":\"/root/figure_worker\"}"` (no thread id!) |
| v2 `wait_agent` | `collaborationwait_agent` | `{"timeout_ms":30000}` | `"{\"message\":\"Wait completed.\",\"timed_out\":false}"` (no result text) |
| code-mode nested `tools.exec_command` | `Bash`, with `tool_use_id:"exec-42804e4e-…"` | as for Bash | as for Bash |

### 2.4 When the tool hooks do **not** fire [RUN S5/S11 + SRC]

- **PostToolUse runs only if `success_for_logging()`** is true and the handler returned `Ok` [SRC core/src/tools/registry.rs:695-721].
  - A **failed apply_patch** (`Update File: missing.md`) gets PreToolUse but **no PostToolUse**. The failure text exists only in the rollout `custom_tool_call_output`: `"apply_patch verification failed: Failed to read file …"`.
  - **Malformed arguments** (`"{not json"`, or a string where an i32 is expected) get **no hook at all**. The rollout has the `function_call` and `function_call_output: "failed to parse function arguments: …"`.
  - A **long-running command** that returns `Process running with session ID N` gets PreToolUse only. PostToolUse is skipped while `process_id` is set [SRC core/src/tools/context.rs:438-445]. In S5 the process was killed at turn end (rollout `exit_code:-1`, `status:"failed"`, recorded after `task_complete`), and **no PostToolUse was ever emitted**.
- **A sandbox-denied write that fails** (`echo x > /etc/…` gives EROFS with exit 1) **does** get PostToolUse. Its text is `"/bin/bash: line 1: /etc/vacant_forbidden_probe2: Read-only file system\n"`. It is, however, **dropped from both `--json` and the rollout `event_msg` items** (see §4).
- **Never hooked:**
  - hosted `web_search_call`;
  - client `tool_search_call`;
  - the outer code-mode `exec` custom tool (S4: only the nested calls fired);
  - reasoning items and assistant messages.

### 2.5 Hook ordering and concurrency [RUN S10, S2]

- One response carried three calls: `call_1_0` (`sleep 0.5; cat`), `call_1_1` (a write) and `call_1_2` (MCP).
- PreToolUse fired for 1_0, 1_1 and 1_2 within 11 ms.
- PostToolUse then fired in completion order: 1_2, then 1_1, then 1_0.
- The parent's `wait_agent` PreToolUse interleaves with the child's hooks.
- Every hook's `ppid` is the codex process.
- [SRC engine/mod.rs `can_apply_control_effects` is Sync-only] [INF] Hooks run synchronously per call, **so Vacant's hook latency adds directly to tool latency**. `async:true` hooks would avoid that, but they cannot block and are capped at 8.

---

## 3. (b) `codex exec --json` [RUN]

- **Top level:**
  - `thread.started{thread_id}`, `turn.started{}` and `turn.completed{usage}`;
  - `item.started|item.completed{item}` and `error`.
  - It has **no `turn_id` and no call ids**.
  - `usage` counts **only the root thread**: S2 reported 80 input tokens, which is 8 root requests × 10; the sub-agent's 3 requests are missing.
- **Items seen:**
  - `reasoning{text}` and `agent_message{text}`.
  - `command_execution{command:"/bin/bash -lc '…'", aggregated_output, exit_code, status: in_progress|completed|failed}`. `failed` means a non-zero exit.
  - `file_change{changes:[{path, kind: add|update}], status}`: **no content or diff**.
  - `mcp_tool_call{server, tool, arguments, result{content,_meta,structured_content}, error, status}`.
  - `web_search`, emitted with a **duplicate key**: `{"id":"item_3","type":"web_search","id":"ws_4_0",…}`. A last-key-wins parser loses `item_3`.
  - `collab_tool_call{tool: spawn_agent|wait|close_agent, sender_thread_id, receiver_thread_ids, prompt, agents_states{<tid>:{status,message}}}` (v1).
  - `error{message}`, e.g. the model-reroute notice.
- **Missing:**
  - every step **inside** a sub-agent (S2, S13);
  - v2 `spawn_agent` (S13 shows only `wait`, with empty `receiver_thread_ids`);
  - failed apply_patch, sandbox-denied commands, `tool_search`, and hook runs;
  - the completion of a background process that outlives the turn (S5: `item.started` with no `item.completed`).

---

## 4. (c) Rollout files [RUN]

- **Location:** `$CODEX_HOME/sessions/YYYY/MM/DD/rollout-<local-ts>-<thread_id>.jsonl`. There is **one file per thread**: the root, and **each** sub-agent.
- **Hooks give the path directly:** `transcript_path`, and `agent_transcript_path` in SubagentStop.
- **`codex exec resume --last` appends to the same file.** It writes a new `task_started` / `turn_context` pair with a new `turn_id`; the hook `SessionStart.source` is `"resume"`.
- Other state (`state_5.sqlite`, `logs_2.sqlite`, `thread_history_1.sqlite`, `goals_1.sqlite`, `memories_1.sqlite`, `queue_1.sqlite`) is not needed for capture.

**Envelope:** `{"timestamp":"…Z","ordinal":<int>,"type":…,"payload":{…}}`. `ordinal` is a per-file sequence number; a forged line without it is detectable, but it is not a MAC.

| `type` / `payload.type` | fields that matter |
|---|---|
| `session_meta` | `id` (thread), `session_id` (root session), `parent_thread_id`, `cwd`, `originator` (`codex_exec`, or the app-server client name), `cli_version`, `source` (`"exec"`, or `{"subagent":{"thread_spawn":{parent_thread_id, depth, agent_path, agent_nickname, agent_role}}}`), `thread_source` (`user`/`subagent`), `agent_nickname`, `agent_path` (v2 `/root/figure_worker`), `model_provider`, `multi_agent_version`, `base_instructions` (the full system prompt) |
| `turn_context` | `turn_id`, `root_turn_id` (a sub-agent's = the parent's turn), `model`, `approval_policy`, `sandbox_policy`, `permission_profile` (writable roots), `multi_agent_version`, `collaboration_mode.settings.reasoning_effort` |
| `world_state` | AGENTS.md, environments; `{"environments":{"subagents":"- <tid>: Hypatia"}}` updates |
| `event_msg/task_started`, `task_complete` | `turn_id`, `last_agent_message`, `duration_ms` |
| `response_item/message` | role `developer` (instructions, skills), `user` (prompt; env context; **injected** `<subagent_notification>` with `content_item_kinds:["multi_agent.subagent_notification"]`), `assistant` |
| `response_item/reasoning` | `summary`, `content`, `encrypted_content` |
| `response_item/function_call` | `name`, `namespace` (`mcp__docs`, `multi_agent_v1`, `collaboration`), `arguments` (raw string), `call_id`, `internal_chat_message_metadata_passthrough.turn_id` |
| `response_item/custom_tool_call` | `name` (`apply_patch` / code-mode `exec`), `input` (raw patch or JS), `call_id` |
| `response_item/function_call_output` / `custom_tool_call_output` | `call_id`, `output`. Shell output text includes `Process exited with code N` |
| `response_item/tool_search_call` / `tool_search_output` | the deferred-tool discovery step (MCP and multi-agent tools are **deferred** behind `tool_search` for `gpt-5.5`) |
| `response_item/web_search_call` | `action{type:"search",query}` only |
| `response_item/agent_message` (v2) | `author`, `recipient` (agent paths); `content` = `"Message Type: NEW_TASK|FINAL_ANSWER\nTask name…\nSender…\nPayload:"` + payload (`encrypted_content` for NEW_TASK) |
| `inter_agent_communication_metadata` (v2) | `{"trigger_turn":bool}` |
| `token_usage_record` | **`response_id`**, `thread_id`, `turn_id`, `session_id`, `root_turn_id`, `usage`, `turn_token_usage`, `thread_token_usage` |
| `event_msg/item_completed` `CommandExecution` | `id` = call_id (or `exec-<uuid>` in code mode), `process_id`, `command` argv, `cwd`, **`parsed_cmd[{type:read,name,path}|{type:search,query,path}|{type:unknown}]`**, `source`, `status`, `stdout`, `stderr`, `exit_code`, `duration`, `started_at_ms`, `completed_at_ms` |
| `… FileChange` | `changes{<abs path>:{type:"add",content}|{type:"update",unified_diff,move_path}}`, `stdout` |
| `… McpToolCall` | `server`, `tool`, `arguments`, `readOnlyHint`, `result{content,isError,_meta}` |
| `… WebSearch` | `query`, `action` |
| `… CollabAgentToolCall` (v1) | `tool` (`spawn_agent`/`wait`/`close_agent`), `sender_thread_id`, `receiver_thread_ids`, `receiver_agents[{thread_id,agent_nickname}]`, `prompt`, `model`, `reasoning_effort`, `agents_states` |
| `… SubAgentActivity` (v2) | `id` = spawn call_id, or `subagent-completed-<child turn>`; `kind: started|completed`, `agent_thread_id`, `agent_path` |
| `… Reasoning`, `AgentMessage`, `UserMessage` | text |

**Linking rules (all confirmed on the S2 files by `traceback_demo.py`):**

- **Call to its output:** `function_call.call_id` = `item_completed.item.id` = `function_call_output.call_id` = hook `tool_use_id`.
- **Call to model response:** the call belongs to the next `token_usage_record.response_id` in the same file.
  - S1: ordinals 9–10 (reasoning, then `function_call call_1_1`) are followed by ordinal 11 `token_usage_record{response_id:"resp_1"}`. Outputs come after.
  - With parallel calls (S10), all three `function_call` records precede the single `resp_1` record.
- **Thread to actor:** `session_meta.id` equals the hook `agent_id`; for the root thread it equals `session_id`.
- **Parent to child:**
  - v1: the parent's `CollabAgentToolCall(spawn_agent).receiver_thread_ids`;
  - v2: `SubAgentActivity(started).agent_thread_id`;
  - the child's `session_meta.parent_thread_id` in both.
- **Lossy spot:** the sandbox-denied command in S11 (`call_1_0`) has `function_call` and `function_call_output` but **no** `item_completed`.
  - Cause: `UnifiedExecError::SandboxDenied` is raised before the command items are emitted [SRC core/src/unified_exec/process.rs:307-340].
  - ⇒ Vacant should build the step list from `function_call`/`custom_tool_call` pairs, and treat `item_completed` as enrichment only.

**Integrity [RUN S9]:** the agent's shell appended a forged line to its own rollout. The line sits between ordinals 13 and 15, has no `ordinal`, and Codex continued writing after it.

---

## 5. (d) Sub-agents and multi-agent in 0.156.1

- **Version selection** [SRC core/src/config/mod.rs:1549-1576] [RUN]:
  - v2 if `features.multi_agent_v2`, or if the model's catalog `multi_agent_version` is `v2` (`gpt-6-*`, `gpt-5.6-sol/terra`);
  - otherwise v1, because `features.multi_agent` is stable and on by default;
  - `[agents] enabled=false` turns sub-agents off.
  - `gpt-5.5` runs v1, where the tools are namespace `multi_agent_v1` and **deferred behind `tool_search`**.
  - Default depth and thread limits: `agent_max_depth`, `agent_max_threads` [SRC].
- **v1 tools:** `spawn_agent{message|items, agent_type, model, reasoning_effort, fork_context}`, `wait_agent{targets, timeout_ms}`, `send_input{target, message|items, interrupt}`, `resume_agent{id}`, `close_agent{target}` [SRC multi_agents/*.rs; RUN S2]. `send_input` and `fork_context` were not exercised.
- **v2 tools** (namespace `collaboration`): `spawn_agent{task_name, message, model, reasoning_effort, fork_turns}`, `send_message`, `followup_task`, `wait_agent{timeout_ms}`, `list_agents`, `interrupt_agent` [RUN S4 probe tool list; S13].
  - The `message` parameter is declared **`"encrypted": true`** in the tool schema, and the child receives it as `{"type":"encrypted_content","encrypted_content":…}` inside an `agent_message` NEW_TASK item.
  - With the mock, the plaintext passed through.
  - [INF] With the real API, the parent-to-child task text would be ciphertext in the hooks, the rollout and the wire alike.
- **Identity per sub-agent:**
  - thread id (UUIDv7);
  - `agent_nickname` (random, e.g. "Hypatia", "Planck", "Feynman");
  - `agent_path` (v2 `/root/<task_name>`, nested as `/root/a/b`; the root is `/root`);
  - `depth`, `agent_role` / `agent_type` (`default`), and its own `model`.
  - The wire meta header `agent_name` is `/root` for **every** v1 thread (S2), but the v2 path in S13.
  - OTEL `agent_name` is the nickname for v1 sub-agents.
- **Model override [RUN S9]:** `spawn_agent{model:"gpt-6-luna", reasoning_effort:"low"}` produced:
  - request body `model: gpt-6-luna`, meta `reasoning_effort: low`;
  - hooks `model: "gpt-6-luna"`;
  - child `turn_context.model: gpt-6-luna`.
  - The child ran in **code mode** because that model is `code_mode_only`, so its steps got `exec-<uuid>` ids.
  - The allowed override list in the spawn tool description comes from the catalog (`gpt-6-astra/sol/luna`, `gpt-5.6-sol/terra`).
- **Sub-agents share the workspace and sandbox with the parent** (S2: the child wrote `figure.txt`, which the parent then read). They run concurrently with the parent's `wait_agent`.
- **Hand-offs are observable** (v1: spawn `prompt`, the child's `UserPromptSubmit.prompt`; return: `wait_agent` output, `<subagent_notification>` user message, `SubagentStop.last_assistant_message`).
  - These are **self-reports**: "Wrote 421,300" is the sub-agent's claim, not proof.
  - The actual effect must come from the child's own tool steps.
- **app-server [RUN S8]:** the stdio JSON-RPC stream delivered the child's `item/started|completed`, `hook/started|completed`, `turn/started|completed` and `thread/tokenUsage/updated` with the **child's `threadId`**.
  - Items carry `id` = call_id. `commandExecution.commandActions[{type:"read",path}]` is present. `fileChange.changes[].diff` holds the content.
  - `hook/completed.run` = `{id, eventName, handlerType, executionMode, scope, sourcePath, source, status, durationMs, entries:[]}` (the hook I/O is not included).
  - This is the only channel that streams child steps **live** without hooks.
  - `turn/diff/updated` came only for the root thread's apply_patch changes, not for the child's shell write.

---

## 6. Which model, which turn

| question | answer in 0.156.1 |
|---|---|
| Which model **response** emitted call X? | rollout: the next `token_usage_record.response_id` after the `function_call` [RUN]. On the wire it is the response id itself. Hooks cannot tell [RUN] |
| Which model (slug)? | hook `model`, `turn_context.model`, wire body `model`. All give the **requested** slug [RUN]. The served model is visible only via the `openai-model` header, and Codex surfaces it as a one-time `--json` error (S6). Codex reads the served model from that header or `response.headers`, **not** from `response.model` in the body [SRC codex-api/src/sse/responses.rs:203-217] |
| Reasoning effort | wire meta `reasoning_effort`, `CollabAgentToolCall.reasoning_effort`, child `turn_context.collaboration_mode.settings.reasoning_effort` [RUN] |
| Reasoning content | `gpt-5.5` requests `reasoning:{effort}` with no summary (catalog `default_reasoning_summary:"none"`) and `include:["reasoning.encrypted_content"]` [RUN]. [INF] With the real API, the rollout would hold an opaque `encrypted_content` and little or no readable "why" |
| Wire join keys | headers `session-id`, `thread-id`, `x-codex-window-id`, `x-openai-subagent: collab_spawn`, `x-codex-parent-thread-id`; `x-codex-turn-metadata` = `{installation_id, session_id, thread_id, agent_name, turn_id, window_id, context_window_id, request_kind:"turn", root_turn_id, thread_source, turn_trigger:"exec", sandbox:"seccomp", sandbox_mode, model, reasoning_effort, …}`; also mirrored in body `client_metadata` [RUN] |

---

## 7. (e) What is NOT observable (or only partly)

1. **Content and paths of shell writes.** Only the command string is captured; `parsed_cmd` is `unknown` for redirects [RUN].
   - Writes by background processes after PostToolUse, or never completed (S5), are invisible.
   - Side effect seen: after the S5 run the workspace contained **empty `.agents/ .codex/ .git/` directories** that no tool call wrote [RUN]. [INF] These are mount points for the read-only protected sub-paths. A snapshot diff will blame them on no one.
2. **Hosted web search results** (only the query) [RUN]. Content fetched *inside* an MCP server is visible only as the server's returned result [RUN].
3. **Code-mode cell internals.** JavaScript control flow, `store`/`load` values across cells, and which cell issued a nested call are not linked by id [RUN S4]. The outer `exec` cell has no hook.
4. **Response-level attribution in hooks** (no `response_id`). **Exit code in the Bash `PostToolUse`** (it is only in the rollout item or in the `function_call_output` text) [RUN].
5. **Failed steps in live channels:**
   - failed apply_patch has no PostToolUse and no `--json` item;
   - malformed calls have no hook;
   - sandbox-denied commands have no `--json` item and no rollout `item_completed`.
   All of them are still in the rollout's `function_call`/`output` pairs [RUN].
6. **v2 hand-off text** with a real model, `"encrypted": true` [RUN schema; INF effect]. The v2 `wait_agent` result carries no answer text; the answer arrives as an `agent_message` [RUN].
7. **Served model** (except the reroute warning) and **reasoning content** (encrypted) [RUN / INF].
8. **Integrity of Codex's own logs.** The rollout is agent-writable when `CODEX_HOME` is writable in the sandbox [RUN S9]. OTEL is batched fire-and-forget [RUN S7: 7 POSTs]. `notify` is fire-and-forget (agent-codex.md §3.6).
9. **Attribution under concurrency.** Parallel calls and parent/child threads overlap [RUN S10/S2].
10. **Side channel noticed.** In S7 Codex POSTed `{"turn_ids":["5a815a92-…"]}` to `<provider base_url>/analytics/codex/turn-costs` with UA `codex-cli` [RUN]. The trigger is not established (the analytics queue or OTEL). A mock or proxy upstream must answer or ignore non-`/responses` paths.

---

## 8. OTEL as a proxy-free, hook-free channel [RUN S7]

```
-c 'otel.exporter={otlp-http={endpoint="http://127.0.0.1:18777/v1/logs",protocol="json"}}'
-c 'otel.trace_exporter={otlp-http={endpoint="http://127.0.0.1:18777/v1/traces",protocol="json"}}'
```

- **Log events seen:**
  - `codex.conversation_starts` (provider, `approval_policy`, `sandbox_policy`, `mcp_servers`, model);
  - `codex.user_prompt` (`prompt:"[REDACTED]"` unless `otel.log_user_prompt=true`);
  - `codex.api_request`, `codex.sse_event`, `codex.tool_decision{call_id, decision:"approved", source:"Config"}`;
  - **`codex.tool_result{tool_result_seq, tool_name, tool_namespace, call_id, duration_ms, success, output_truncated, agent_name, arguments, output, mcp_server, conversation.id, model}`**.
- It **includes sub-agent tool results**: `agent_name:"Carver"`, with `conversation.id` = the child thread.
- Traces are mostly internal spans (`fs.get_metadata`, `append_items`, `codex.hooks.command`, `build_tool_call`, `handle_output_item_done` …).
- It is a good **second, independent witness** for cross-checking hook records. It is not an integrity anchor.

---

## 9. Capture recipe for Vacant: a complete step-level trajectory with actor ids

**At launch**, append to the user's own `codex` invocation. Nothing is written to their `config.toml`.

```
--enable hooks
-c 'hooks.<E>=[{hooks=[{type="command",command="vacant hook codex <E>",timeout=30}]}]'
      for E in SessionStart UserPromptSubmit PreToolUse PostToolUse SubagentStart SubagentStop Stop SessionEnd
      (SessionEnd timeout ≤3)
-c 'hooks.state={"/<session-flags>/config.toml:<snake E>:0:0"={trusted_hash="sha256:…",enabled=true},…}'
      hashes via run_probe.py:hook_hash, i.e. agent-codex.md §3.3
optional: -c otel.exporter / otel.trace_exporter → a local Vacant OTLP sink
          (second witness; set otel.log_user_prompt=true only with consent)
optional: --json → keep for the root thread's live UI only
```

- The session-flag hooks reach sub-agents [RUN S12].
- If the person uses the TUI, the same hooks, rollout and OTEL apply [INF: same core]; `--json` does not exist there.
- `codex app-server` embedding gives the same data live, including child threads [RUN S8].

**At each hook (host process, outside the sandbox):**

1. Append a record to Vacant's **signed hash-chain** (logbook). The record holds:
   - the hook payload verbatim;
   - `recv_ts`;
   - the **actor key** `(session_id, thread = agent_id ?? session_id, agent_type, model, turn_id)`;
   - the **step key** `tool_use_id`.
2. At **PreToolUse / PostToolUse**, add a content hash of the workspace (or of the paths named in `tool_input`) to catch shell writes.
   - Mark the record `concurrent=true` if another call on any thread is between its own Pre and Post (§2.5).
   - This is how Vacant fills the shell-write blind spot. A cheaper form is mtime/size plus sha256 of the changed files, relative to the previous snapshot.
3. At **SubagentStart**, sign the link `(parent session_id, child agent_id, child transcript_path)`.
   - For v1, also join the parent's `PostToolUse(spawn_agent).tool_response.agent_id` to that spawn's `tool_use_id`.
4. At **SubagentStop / Stop / SessionEnd**, sign `sha256` and byte length of the rollout at `agent_transcript_path` / `transcript_path`. That seals it against the post-hoc tampering shown in S9.
   - Record `last_assistant_message` as the actor's **claim**.

**After the run: build the step graph from the rollouts.** `traceback_demo.py` is the working prototype.

1. Build one node per `function_call` / `custom_tool_call` (not per `item_completed`) with:
   - `thread`, `actor` (nickname or path), `model` (from the last `turn_context`), `turn_id`, `response_id` (the next `token_usage_record`), `call_id`, `tool`, `input`, `output`;
   - reads: `parsed_cmd` `read` paths plus MCP result `_meta` plus the injected `<subagent_notification>` / `agent_message`;
   - writes: `FileChange` content and diffs, plus Vacant's snapshot diffs for shell steps.
2. Code-mode nested steps (`exec-<uuid>`) are children of the enclosing `custom_tool_call exec` **by position**; mark them `link=positional`.
3. Check every rollout node against the signed hook records by `(thread, call_id)`.
   - A node with no hook record, or a hook record with no node, is a finding in itself (§2.4 lists the legitimate gaps).
   - Check the rollout's sealed hash as well.

**Trace-back** (demonstrated [RUN]; `python3 traceback_demo.py runs/S2_subagent brief.md 421,300 412,300`):

- **S2** walks this chain:
  1. `brief.md` was written by the root agent, `call_8_0`, `resp_8`.
  2. The root had read the bad value via `multi_agent_v1/wait_agent` (`call_3_0`) and `cat figure.txt` (`call_7_0`).
  3. `figure.txt` was written by the sub-agent **Hypatia** (thread `…aa03c6`, `gpt-5.5`, `resp_5`, `call_5_0`, `printf '421,300\n' > figure.txt`).
  4. Earlier, in `call_4_1`, Hypatia **read the correct `412,300`** from `notes.txt`.
  5. ⇒ **Agent error, attributable to the sub-agent's model response `resp_5`.**
- **S2b** has the same flow with `notes.txt` already saying 421,300. The walk ends at `[ORIGIN] no step in this session wrote notes.txt; it pre-existed` ⇒ **input/requirement error**, and no agent is penalised.
- Both verdicts are heuristic: they rely on value-matching.
  - The root agent, which forwarded the bad value unchecked, is a secondary party.
  - Whether "forwarded without checking" should cost reputation is a policy choice for `reputation.py`, not a capture question.

**Actor ids to key reputation on** (maps to `reputation.py`'s `(stream, branch, substrate)`):

- stream = the Codex **root `session_id`** (or Vacant's own run id);
- branch = **thread id**, with nickname and path as display labels;
- substrate = the **model slug** as requested.
- Keep the served model separately, and only when a proxy or the reroute warning shows one.

---

## 10. Gaps / not verified

- `PermissionRequest`, `PreCompact`/`PostCompact` and `Interrupt` payloads were not triggered (exec forces approval `never`; no compaction or interrupt). Only the schemas were read.
- The interactive TUI was not driven. Hooks, rollout and OTEL there are [INF]; they are the same core.
- `send_input`, `resume_agent`, `fork_context` (v1), and v2 `send_message`/`followup_task`/`fork_turns≠none` were not exercised, so how forked history appears in the child's rollout is unmeasured.
- Real-API behaviour is not measured:
  - the v2 encrypted hand-off (`"encrypted": true`);
  - real `reasoning.encrypted_content` (the mock sent plaintext reasoning);
  - real `openai-model` headers.
- The trigger for the `/analytics/codex/turn-costs` POST (seen once, in S7) is not established.
- `CODEX_HOME` outside /tmp was not re-tested. My write rule kept every home under /tmp, which is sandbox-writable. agent-codex.md reports EROFS for a `/var/tmp` home under `workspace-write` (earlier RUN). Under `danger-full-access` the rollout is always agent-writable [INF].
- `code_mode` cell to nested-call linkage: the runtime `cell_id` exists in source but was not found in any emitted record. The app-server `commandExecution` for code-mode nested calls was not checked.
- Hook latency and cost of per-call workspace snapshots was not measured.
- Windows and macOS were not covered.
