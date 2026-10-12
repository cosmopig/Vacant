# Claude Code 2.1.281: capturing the trajectory for accountability

Date: 2026-09-24. Binary: `/opt/node22/bin/claude` reports `2.1.281 (Claude Code)`.

The question this sheet answers: while a person drives **one** Claude Code session on a general task (not necessarily coding), can Vacant:

1. record **who did what** as it happens: each tool call, what it read and wrote, which model turn issued it, and which agent or sub-agent took the step;
2. when a check on the deliverable fails, **trace back** to the step that introduced the error;
3. tell "the input was wrong" apart from "the agent got it wrong"?

Nothing under `/home/user/Vacant` was modified. No real API key was used and no real model was contacted.

## Evidence tags

- **[RUN]**: I executed it and saw the result.
- **[SRC]**: read in the shipped binary's embedded JS (`strings`), or in the repository's mock.
- **[DOC]**: official docs saved earlier at `scratchpad/cc/doc_*.md`.
- **[INF]**: my inference, not verified.

## Lab (all under `scratchpad/accountability/claude/`)

| File | Role |
|---|---|
| `mock_traj.py` | Scripted offline Anthropic Messages upstream, derived from `ops/intake/mock_model.py`. It detects the role (`ROLE:main` / `ROLE:sub` / `ROLE:sub2`) from the first user message and plays step `k` = the number of prior assistant messages. It can emit parallel `tool_use` blocks, `thinking` blocks and a `request-id` header. It answers a tool-less call (the WebFetch side model) with `side_text`. Response `model` = `"srv:"+requested`, so the server-reported model and the requested model can be told apart. It saves every request body to `out/<run>/mock/bodies/NNN.json`. |
| `hk.py` | One hook for all 31 registered events. It logs the full stdin payload and adds a **correlation probe**: at the moment the hook runs, is the `tool_use_id` already in the transcript, and in which record? It also logs transcript line counts. With `SNAP=1` it logs a sha256 snapshot of the workspace at Pre/Post of every Bash call and at SessionStart/End. |
| `run_cc.py <label> <flags>` | Real `claude -p` with isolated `HOME`, `ANTHROPIC_API_KEY=sk-fake-offline-000`, `ANTHROPIC_BASE_URL=http://127.0.0.1:<mock>`, `CLAUDE_CODE_TMPDIR` inside the run dir, one `--settings` file, `--output-format stream-json --verbose --include-hook-events`, and `--permission-mode acceptEdits`. `NODE_EXTRA_CA_CERTS` trusts a self-signed local HTTPS page, because WebFetch upgrades `http://` to `https://`. |
| `web_https.py`, `tls/` | The local HTTPS page. |
| `mcp_mail.py` | A stdio MCP server with `send_email`, a side effect written to `outbox.jsonl`, and `fail_tool`. |
| `otel_rx.py` | A local OTLP/HTTP-JSON sink. |
| `summarize.py`, `analyze_corr.py`, `trace_claude.py` | Readers. `trace_claude.py` is the post-hoc blame tracer (§6). |

The scenario is a **non-coding task**: write `report.md`, a "Springfield brief" with the population from `data/cities.csv` (30720) and the mayor from a web page. The main agent does the following:

1. Reads two files in parallel.
2. Hands off to a `general-purpose` sub-agent. The sub-agent runs WebFetch, then Bash `mkdir`, then Write `notes/mayor.txt`.
3. Runs a **buggy Bash** step: `cut -c1-4` turns 30720 into 3072 in `notes/derived.txt`.
4. Reads the notes.
5. Writes `report.md` with `Population: 3072`, then Edits it.
6. Makes three failing calls in one message: Bash exit 1, Read of a missing file, Edit with no match.
7. Runs WebFetch itself.
8. Runs a Bash `sed` that silently changes `Alice` to `Alicia` in `report.md`.
9. Optionally sends an MCP email that carries the wrong number.

| Run | Flags | What it adds |
|---|---|---|
| `traj` | (http, first try) | WebFetch fails on the https upgrade, which gives PostToolUseFailure payloads |
| `T1` | `traj+ckpt` | Baseline full scenario, with file checkpointing |
| `T2_bg` | `traj+bg` | Sub-agent in the **default background mode** |
| `T3_haiku` | `traj+haiku` | `Agent.model="haiku"` |
| `T4_nest` | `traj+nest` | The sub-agent spawns a sub-sub-agent |
| `T5_deny` | `traj+deny` | Bash not allowed, default permission mode |
| `T6_parmcp` | `traj+par+mcp` | Parallel mutating calls, background Bash, MCP side effect and MCP error |
| `T7_full` | `traj+par+mcp+snap+fc+ckpt` | Workspace snapshots, FileChanged on an existing file |
| `T8_otel` | `traj+otel` | OpenTelemetry logs to the local sink, with raw API bodies |
| `T9_badsrc` | `traj+snap+badsrc` | The **source web page itself is wrong** ("Bob Stone") |
| `T10_think` | `traj+think` | The mock emits a `thinking` block before the buggy Bash |

All runs exited 0. Every run is reproducible with `python3 run_cc.py <label> <flags>`.

---

## 0. Decision-relevant summary

1. **Every step is joinable after the fact by `tool_use_id`** [RUN]. The same id appears in:
   - the hook payloads (`PreToolUse`, `PostToolUse`, `PostToolUseFailure`, `PostToolBatch.tool_calls[]`);
   - the transcript `tool_use` / `tool_result` blocks;
   - stream-json;
   - OTel `tool_decision` / `tool_result`;
   - the proxy's view of the model output.

   It is the only key present in all channels. Across 11 runs, after `SessionEnd`, all 177 distinct hook `tool_use_id`s (177/177) were found in the main or sub-agent transcript.
2. **Hooks give "what the tool did" but not "which model turn issued it"** [RUN] [DOC].
   - Payloads carry `session_id`, `prompt_id`, `agent_id`/`agent_type` (inside sub-agents only), `tool_use_id`, `tool_input` and `tool_response`.
   - They carry **no** `message.id`, **no** model, **no** request id, and no preceding assistant text or thinking.
   - Docs: only SessionStart may carry `model`.
3. **Looking up the model turn from the transcript inside the hook is unreliable** [RUN].
   - At `PreToolUse` the issuing `tool_use` record was already in the transcript in only **26 of 97** invocations (27%).
   - At `PostToolUse` it was there in 75 of 79 (95%).
   - At `PostToolUseFailure` it was there in 15 of 15.
   - The `tool_result` record was **never** present at Post time.
   - ⇒ Log live from hooks (signed, synchronous). Join to the transcript at `SessionEnd`, when the transcript was complete in 6/6 measured runs. Do not join at `Stop`: the main transcript still lacked 3 lines then. Do not join at `SubagentStop`: the sub-agent file lacked its last 3 lines.
4. **The model per step is `message.model` in the transcript, and that is the value the server reports** [RUN].
   - The mock answered `srv:claude-opus-5-5` to a request for `claude-opus-5-5`. The transcript, stream-json and OTel `api_request.model` all recorded `srv:claude-opus-5-5`.
   - The requested model appears only in the proxy body, in `cost-state.modelUsage` (`claude-opus-5-5[1m]`) and in `Agent.tool_response.resolvedModel`.
   - An accountability record needs both, and only the proxy sees the request.
5. **Sub-agents are fully attributable** [RUN]:
   - hook `agent_id` / `agent_type`;
   - their own transcript `…/<session_id>/subagents/agent-<agent_id>.jsonl` (`isSidechain:true`, `agentId`);
   - a `agent-<id>.meta.json` holding **`toolUseId`** (the parent's `Agent` call), `parentAgentId` (nested) and `spawnDepth`;
   - proxy headers `x-claude-code-agent-id` and `x-claude-code-parent-agent-id` (nested);
   - stream-json `parent_tool_use_id`.

   Caveat: a sub-agent's hook `transcript_path` points to the **main** transcript, and SubagentStart has no parent link.
6. **Background is the default for `Agent`** (`run_in_background` defaults to true in the schema) [RUN].
   - Main-thread and sub-agent steps then **interleave**.
   - In `T2_bg` the main agent Read `notes/mayor.txt` before the sub-agent wrote it, which gave a PostToolUseFailure.
   - The sub-agent's result comes back as a `UserPromptSubmit` whose prompt is a `<task-notification>` naming `<tool-use-id>`.
   - Attribution holds, because every hook carries `agent_id`. Blame ordering has to use timestamps plus `tool_use_id`, not position in a single log.
7. **Files written by Bash are invisible in every Claude-side channel** [RUN]:
   - Bash `tool_input` has only `command` and `description`.
   - `tool_response` has only `{stdout,stderr,interrupted,isImage,noOutputExpected}`.
   - Checkpointing tracks Write/Edit only.

   A hook that hashes the workspace at `PreToolUse(Bash)` and `PostToolUse(Bash)` fixes this for **foreground** Bash. Mutating tools in one message run **serially** (measured), so each Pre/Post window belongs to one call. It does **not** fix `run_in_background` Bash: `notes/late.txt` stayed unattributed.
8. **Some steps never reach a hook** [RUN]:
   - A tool call rejected by input validation (Edit with no match, `<tool_use_error>`) fired **neither** PreToolUse nor PostToolUseFailure. It exists only in the transcript as an `is_error` result.
   - A permission-denied call fired PreToolUse and `PermissionRequest` (which has **no** `tool_use_id`), but no Post* event and no `PermissionDenied` (that event is for auto-mode). It appears in the result `permission_denials[]`.
   - The WebFetch side-model call (the model that turns the page into the text the agent reads) is **not in the transcript at all**. It is visible only in the proxy, or in OTel as `query_source:"web_fetch_apply"`.
9. **The trace-back works end to end on this data** [RUN]: `trace_claude.py`, §6.
   - Population check: `report.md` Write (main, `msg_main_4_10`) ← Read `notes/derived.txt` ← Bash `toolu_main_2_0` (fs-diff). The correct 30720 had been visible to the same actor at `toolu_main_0_1`, so the verdict is **AGENT_ERROR**.
   - With the source page itself wrong (`T9_badsrc`): Write ← `Agent` hand-off ← sub-agent WebFetch. The reference was never visible, so the verdict is **INPUT_ERROR candidate**.
   - Without workspace snapshots (`T1`) the same trace **dead-ends** at the Bash-written file.
10. **Transcripts are not evidence by themselves** [RUN] [INF]:
    - They are plain JSONL under `~/.claude/projects/`, written asynchronously.
    - They are subject to a 30-day retention sweep (OTel `retention_sweep` reports `period_days:"30"` [RUN]).
    - They can be written by the agent's own Bash [INF].

    Vacant must hash them into its own signed chain at `SessionEnd`, or per step, and copy them out.

---

## 1. Capture channels compared

| Channel | Who / what it tells | When available | Blind spots (measured) |
|---|---|---|---|
| **Hooks** (`--settings` JSON, command hooks, synchronous) | `tool_use_id`, tool name, **normalized** input, structured result, error, `agent_id`/`agent_type`, `prompt_id`, `duration_ms` | Live: Pre before execution; Post before the next model call | No model, message id or request id. Validation-rejected calls are silent. Bash file effects are missing. Denials only as `PermissionRequest` without `tool_use_id`. Fail-open (see `understand/agent-claude.md`). |
| **Transcript JSONL** (`transcript_path`, `subagents/`) | The full conversation: assistant records with `message.id`, **`message.model`**, `requestId`, thinking, text, `tool_use`; user `tool_result` + `toolUseResult`; attachments (system prompt snapshot, model identity, file-changed notices) | Async; complete at `SessionEnd` [RUN] | Side-model calls are missing. Sub-agent `toolUseResult` is missing (success). Raw web page is missing. Agent-writable. 30-day retention. |
| **stream-json stdout** (`-p --output-format stream-json --verbose`) | Same messages as the transcript plus `request_id`, **`parent_tool_use_id`** on sub-agent messages, `system/task_started{task_id,tool_use_id,subagent_type,spawn_depth,prompt}`, `task_progress`, `task_notification`, `init` (tools, MCP, model, `permissionMode`), `hook_started`/`hook_response` | Live | Headless only. Sub-agent `user` events have no `tool_use_result`. Side calls are missing. |
| **Proxy** (`ANTHROPIC_BASE_URL` → Vacant) | The **exact** request (the full context the model saw, including the requested model) and the raw response (un-normalized tool input, served model). Headers `x-claude-code-session-id`, `x-claude-code-agent-id`, `x-claude-code-parent-agent-id` (depth ≥ 2). Side calls (WebFetch summarizer) with raw page content. | Live | Tool **execution** is not visible (what Bash did, what Write wrote). Join to steps via `request-id` ↔ transcript `requestId`, or response `message.id`. |
| **OTel logs** (`CLAUDE_CODE_ENABLE_TELEMETRY=1`, OTLP) | `tool_decision{decision,source,tool_use_id}`, `tool_result{tool_use_id,success,tool_input,error}`, `api_request{model,request_id,query_source,agent.name}`, `api_request_body` / `api_response_body{message.id,request_id}`, `assistant_response{query_source:"web_fetch_apply"}`, `subagent_completed`, `hook_*`, `retention_sweep` | Batched (300 ms here) | `tool_result`/`tool_decision` from sub-agents carry **no agent attribute**. `api_request_body` truncated at **61439 chars** (`body_truncated:"true"`) [RUN]. Exporter config is visible to the agent's environment [INF]. |
| **Workspace snapshots from hooks** (Vacant's own) | Which files each foreground Bash call changed | Live | Background Bash. Concurrent sub-agents writing at the same time [INF]. Processes outside Claude. |
| `FileChanged` hook | That a watched file changed (`add`/`change`) | **Delayed and coalesced** (§2.10) | No `tool_use_id`, no `agent_id`. Watch paths under a directory that did not exist at SessionStart never fired. |
| File checkpointing (`CLAUDE_CODE_ENABLE_SDK_FILE_CHECKPOINTING=true` in `-p`) | `file-history-snapshot` / `file-history-delta{messageId,trackingPath,backup{backupFileName,version}}` | Live | Main-thread Write only in our runs. Not sub-agent Write, not Bash, and no new delta for a later Edit of the same file in the same prompt. |

---

## 2. Hook payloads (exact, from `hooks.jsonl` of the runs; `$OUT` = run dir)

### 2.1 Common fields [RUN]

The following keys were seen, by event:

- **SessionStart**: `session_id, transcript_path, cwd, hook_event_name, source:"startup"`. No `prompt_id`, no `model` in 2.1.281 `-p`.
- **UserPromptSubmit**: `session_id, transcript_path, cwd, prompt_id, permission_mode, hook_event_name, prompt`. No `source` field was observed.
- **Tool events**: common keys plus `effort:{level:"medium"}`, plus `agent_id` and `agent_type` **only inside a sub-agent**.
- **SessionEnd**: `session_id, transcript_path, cwd, prompt_id, hook_event_name, reason:"other"`.

Every hook in a session carried the same `prompt_id` (UUID), including sub-agent hooks and the background `<task-notification>` turn. It equals the transcript `promptId` and OTel `prompt.id` [RUN].

`transcript_path` is `$HOME/.claude/projects/<cwd with / and . replaced by ->/<session_id>.jsonl` [RUN]. Inside a sub-agent it is still the **main** file.

### 2.2 PreToolUse (main vs sub-agent) [RUN]

```json
{"session_id":"4d3f…","transcript_path":"…/4d3f….jsonl","cwd":"$OUT/proj","prompt_id":"95b18340-…",
 "permission_mode":"acceptEdits","effort":{"level":"medium"},"hook_event_name":"PreToolUse",
 "tool_name":"Read","tool_input":{"file_path":"$OUT/proj/data/cities.csv"},"tool_use_id":"toolu_main_0_1"}
```

Inside a sub-agent, the payload adds `"agent_id":"ae25e3db07190787f","agent_type":"general-purpose"`.

`tool_input` is the **normalized** input [RUN]. For Edit, `"replace_all":false` was injected although the model did not emit it. The transcript and the history re-sent to the model are mutated the same way. Only the proxy sees the raw bytes of the model's `input_json_delta`.

### 2.3 PostToolUse `tool_response` by tool [RUN]

| Tool | `tool_response` |
|---|---|
| Read | `{"type":"text","file":{"filePath","content","numLines","startLine","totalLines"}}` (full file content) |
| Write | `{"type":"create"\|"update","filePath","content","structuredPatch":[],"originalFile":null\|<previous text>,"userModified":false}` |
| Edit | `{"filePath","oldString","newString","originalFile":"<full text before>","structuredPatch":[{"oldStart","oldLines","newStart","newLines","lines":["-# Brief","+# Springfield Brief",…]}],"userModified":false,"replaceAll":false}` |
| Bash (fg) | `{"stdout":"","stderr":"","interrupted":false,"isImage":false,"noOutputExpected":false}`; **no file list** |
| Bash `run_in_background:true` | same plus `"backgroundTaskId":"btgho06h7"`. PostToolUse fires at **launch** (58 ms); the file it wrote appeared later, unattributed |
| WebFetch | `{"bytes":82,"code":200,"codeText":"OK","result":"<SIDE-MODEL summary>","durationMs":8,"url":"https://…"}`; raw page absent |
| Agent (fg) | `{"status":"completed","prompt","agentId","agentType","content":[{"type":"text","text":"<final report>"}],"resolvedModel":"claude-opus-5-5[1m]","totalDurationMs","totalTokens","totalToolUseCount","usage",…,"toolStats":{"readCount","searchCount","bashCount","editFileCount","linesAdded","linesRemoved","otherToolCount"},"harnessNoteCount","harnessTailCount","harnessSectionHash"}` |
| Agent (bg, default) | `{"isAsync":true,"status":"async_launched","agentId","description","resolvedModel","prompt","outputFile":"<CLAUDE_CODE_TMPDIR>/…/<sid>/tasks/<agentId>.output","canReadOutputFile":true}` |
| MCP (`mcp__mail__send_email`) | `"{\"message_id\":\"MAIL-0001\"}"`: a **string** (the serialized `structuredContent`), plus top-level `"mcp_server":{"name":"mail","source":"dynamic"}` |

`PostToolUse.tool_response` equalled the main transcript's `toolUseResult` in 10 of 10 compared calls [RUN, T10].

### 2.4 PostToolUseFailure [RUN]

The payload has `tool_input`, `tool_use_id`, `error`, `is_interrupt`, `duration_ms`, and `mcp_server` for MCP tools. Observed `error` strings:

- Bash: `"Exit code 1\ncat: missing_source.txt: No such file or directory"`
- Read: `"File does not exist. Note: your current working directory is $OUT/proj."`
- WebFetch on http: `"error:100000f7:SSL routines:OPENSSL_internal:WRONG_VERSION_NUMBER"`
- MCP `isError`: `"upstream said no"`

**Not fired** for Edit with no match. That call became `tool_result` `"<tool_use_error>String to replace not found in file.…"` with no hook at all [RUN, 5 runs].

### 2.5 PostToolBatch [RUN]

Exactly one per assistant message, after all its calls, before the next request. It has `tool_calls:[{tool_name, tool_input, tool_use_id, tool_response}]`. Here `tool_response` is the **model-visible** string, not the structured object:

- Read: `"1\tcity,population\n2\tSpringfield,30720\n3\t"`
- Bash: `"(Bash completed with no output)"`
- Agent: `[{"type":"text","text":"[Subagent hand-back] … The report follows:\n  SUBAGENT-REPORT: …\nagentId: ae25… (use SendMessage …)\n<usage>subagent_tokens: 19\ntool_uses: 3\nduration_ms: 882</usage>"}]`

Sub-agent batches carry `agent_id`.

### 2.6 Parallel execution order [RUN]

- **Read-only calls run concurrently.** Two Reads, or Read with `cat`, gave PreToolUse, PreToolUse, then Post, Post in arbitrary order.
- **Mutating calls in one message ran serially.** In T6 with Bash, Bash, Write and bg-Bash:
  ```
  Pre(3_0) 1996ms → Post(3_0) 3075 → Pre(3_1) 3108 → Post(3_1) 4163 → Pre(3_2) 4196 → Post(3_2) 4236 → Pre(3_3) 4271 → Post(3_3) 4330 → PostToolBatch
  ```
  Per-call Pre/Post workspace diffs are therefore attributable within one actor.
- With a **background sub-agent**, main and sub hooks interleave (T2_bg). Diffs are then ambiguous across actors [INF].

### 2.7 Sub-agent lifecycle [RUN]

**SubagentStart**:

```json
{"session_id","transcript_path":"<MAIN>","cwd","prompt_id","agent_id":"ae25e3db07190787f","agent_type":"general-purpose","hook_event_name":"SubagentStart"}
```

- No parent `tool_use_id`.
- No parent agent id, even for a nested sub-agent (T4).
- The link lives in `agent-<id>.meta.json`, and in stream-json `task_started.tool_use_id`.

**SubagentStop**:

```json
{…,"agent_id","agent_type","stop_hook_active":false,
 "agent_transcript_path":"$HOME/.claude/projects/<cwd>/<sid>/subagents/agent-ae25e3db07190787f.jsonl",
 "last_assistant_message":"SUBAGENT-REPORT: …","background_tasks":[],"session_crons":[]}
```

**Background completion** arrives as `UserPromptSubmit` with:

```
prompt = "<task-notification>\n<task-id>acda…</task-id>\n<tool-use-id>toolu_main_1_0</tool-use-id>\n<output-file>…</output-file>\n<status>completed</status>\n<summary>…</summary>\n<note>…</note>\n<result>SUBAGENT-REPORT: …</result>\n<usage>…</usage>\n</task-notification>"
```

It is the same `prompt_id` [RUN, T2_bg].

### 2.8 Stop, SessionEnd, MessageDisplay [RUN]

- **Stop**: `{…,"stop_hook_active":false,"last_assistant_message":"Report ready: report.md","background_tasks":[],"session_crons":[]}`
- **SessionEnd**: `{…,"reason":"other"}`
- **MessageDisplay**: `{"turn_id","message_id":"<uuid>","index":0,"final":true,"delta":"<text>"}`. Its `message_id` is **not** the transcript `uuid` nor the API `message.id`.

### 2.9 Permission denial (T5, default mode, Bash not allowed) [RUN]

```json
{"hook_event_name":"PermissionRequest","tool_name":"Bash","tool_input":{"command":"mkdir -p notes && … > notes/derived.txt","description":"derive population"},
 "permission_suggestions":[{"type":"addDirectories","directories":["$OUT/proj/notes"],"destination":"session"},{"type":"setMode","mode":"acceptEdits","destination":"session"}]}
```

- There is no `tool_use_id`. Join to the preceding PreToolUse by `tool_input` equality.
- No `PermissionDenied` and no Post* event.
- The transcript `tool_result` has `is_error:true` and `"This Bash command contains multiple operations. The following part requires approval: …"`.
- The result object has `permission_denials:[{tool_name,tool_use_id,tool_input}]`, and it includes sub-agent denials.

### 2.10 FileChanged [RUN]

Payload: `{…,"hook_event_name":"FileChanged","file_path":"$OUT/proj/report.md","event":"add"|"change"}`.

- It has `prompt_id` but **no** `tool_use_id` and **no** `agent_id`.
- In T1, `report.md` was written by Write at t=1.97 s and edited at t=2.13 s. `add` was delivered at 2.60 s, during the next Bash call. A single `change` at 5.16 s covered both the Edit and the `sed` at about 4.5 s (coalesced).
- It fired for the matcher-seeded `report.md`, and for `brief_request.md` added via `watchPaths` (which existed at start).
- It never fired for `watchPaths` under `notes/`, a directory that did not exist at SessionStart.
- Conclusion: a tripwire, not attribution.

---

## 3. The transcript (`transcript_path`)

### 3.1 Location and files [RUN]

```
$HOME/.claude/projects/<sanitized cwd>/<session_id>.jsonl                       main thread
$HOME/.claude/projects/<sanitized cwd>/<session_id>/subagents/agent-<agentId>.jsonl  one per sub-agent (flat, also nested ones)
$HOME/.claude/projects/<sanitized cwd>/<session_id>/subagents/agent-<agentId>.meta.json
   {"agentType":"general-purpose","description":"Look up the mayor","toolUseId":"toolu_main_1_0","spawnDepth":1,
    "requestShape":"foreground","requestNonInteractive":true}
   nested: {…,"toolUseId":"toolu_sub_0_0","parentAgentId":"aa11132d29748e4a7","spawnDepth":2,…}
$CLAUDE_CODE_TMPDIR/claude-<uid>/<sanitized cwd>/<session_id>/tasks/<agentId>.output   (bg output file, empty here)
```

### 3.2 Record types seen (`type` field) [RUN]

| Type | What it holds |
|---|---|
| `user` | The prompt (`promptId`, `promptSource:"sdk"`, `turnOrigin`, `permissionMode`), or `tool_result` blocks with `toolUseResult` and **`sourceToolAssistantUUID`** |
| `assistant` | **One record per content block**. N parallel `tool_use` blocks from one API message become N records sharing `message.id`, with `apiBlockIndex`. Fields: `message.{id,model,content,stop_reason,usage}`, `requestId`, `effort`, `perTurnEffort`. Thinking is its own record: `{"type":"thinking","thinking":"REASONING-MARKER: …","signature":"…"}` precedes the `tool_use` record with the same `message.id` [RUN, T10]. Thinking never appears in any hook payload. |
| `attachment` | `.attachment.type` ∈ `hook_success` (SessionStart stdout), `environment`, **`model`** (`identity:{modelId:"claude-opus-5-5[1m]",marketingName,knowledgeCutoff}`; in the haiku sub-agent `claude-haiku-4-5-20251001`), `agent_listing_delta`, `skill_listing`, `session_context`, `date`, `remote_session_change`, **`prompt_snapshot`** (the full `systemPrompt` array), `total_tokens_reminder`, `silent_turn_reminder`, **`edited_text_file`** (`{filename,snippet}`: a file Claude had read changed on disk, e.g. by Bash `sed`), `queued_command` (bg notification, `commandMode:"task-notification"`) |
| `system` | `subtype:"stop_hook_summary"` with `hookInfos`, `hookErrors`, `preventedContinuation` |
| Other | `queue-operation` (`enqueue`/`dequeue`/`remove`, `reason:"absorbed_mid_turn"`), `last-prompt{leafUuid}`, `atis-latch`, `cost-state{modelUsage:{"claude-opus-5-5[1m]":…,"claude-haiku-4-5-20251001":…}}`, `file-history-snapshot` / `file-history-delta` (with checkpointing) |

Common fields: `uuid`, `parentUuid`, `isSidechain`, `timestamp`, `sessionId`, `cwd`, `version:"2.1.281"`, `gitBranch`, `entrypoint:"sdk-cli"`, `userType`. Sub-agent records add `agentId`.

### 3.3 Linking [RUN]

- **tool_use → tool_result**: by `tool_use_id`. The result record also has `sourceToolAssistantUUID` equal to the `uuid` of the exact `tool_use` record, and `parentUuid` set to the same value.
- **tool_use → model turn**: `message.id` of the record (`msg_main_4_10`), plus `requestId` (`req_mock_010`, from the response header `request-id`) and `message.model`.
- **Parallel calls**: `parentUuid` forms a **tree, not a chain**. Walking `parentUuid` from the leaf missed 4–9 of the 26–38 `tool_use` + `tool_result` records in every run (`analyze_corr.py`; for example T1 missed `toolu_main_0_1`, `toolu_main_3_1` and 4 results). Reconstruct a turn's context by `message.id` grouping plus `sourceToolAssistantUUID`, not by the `parentUuid` walk.
- **Sub-agent → parent**: the sub-agent file's first record has `parentUuid:null`. The parent link is only in `meta.json.toolUseId`, in `Agent.tool_response.agentId`, and in stream-json `parent_tool_use_id`.
- **What is missing from the sub-agent file**: successful `tool_result` records have **no `toolUseResult`**, so there is no structured Write/Edit result. Take it from the PostToolUse hook, which does carry it.

### 3.4 Completeness over time [RUN] (`analyze_corr.py`, 6 runs)

| When | Main transcript lines | Sub-agent file lines |
|---|---|---|
| at `Stop` | final − 3 | complete |
| at `SessionEnd` | **= final** (6/6) | complete |
| at `SubagentStop` | n/a | **final − 3** (the last assistant text is missing; use `last_assistant_message`) |

---

## 4. Can a hook reliably correlate a tool call to the model message that issued it?

**Live inside the hook: no** [RUN]. Counts are over T1–T6, 191 probe hits:

| Hook | Issuing `tool_use` already in transcript |
|---|---|
| PreToolUse | 26 / 97 |
| PostToolUse | 75 / 79 |
| PostToolUseFailure | 15 / 15 |

The four PostToolUse misses were fast tools: Agent-bg launch, Write, WebFetch, MCP. The payload has no message id or model.

**Post hoc: yes, deterministically** [RUN]. Recipe:

1. Log hooks live, keyed by `tool_use_id`.
2. At `SessionEnd` (or after the process exits) read the main transcript plus `subagents/*.jsonl` plus `*.meta.json`.
3. Build `tool_use_id → {actor: main | agentId, agent_type, parent tool_use_id (meta.toolUseId), message.id, message.model, requestId, timestamp, thinking/text in the same message.id}`.
4. Join the proxy by `request-id`/`requestId` and response `message.id`. Join OTel by `request_id` / `tool_use_id`.

**Concurrency** [RUN]: with a bg sub-agent, hooks from two actors interleave, so ordering must come from timestamps and `tool_use_id`. Headers `x-claude-code-agent-id` equal hook `agent_id` (for example `a11a26b3ab8aa86ea`). Main-thread requests have no agent header. `x-claude-code-parent-agent-id` appears only at depth ≥ 2.

**Model identity per actor** [RUN, T3]:
- A `haiku` sub-agent sent `model:"claude-haiku-4-5-20251001"`, and its transcript recorded `srv:claude-haiku-4-5-20251001` (the server-reported value).
- The **WebFetch side call inside that haiku sub-agent used `claude-opus-5-5`**, the session's small or fast model setting, not the actor's model. "Which model produced this text" can differ from "which actor ran this step".

---

## 5. What is NOT observable (and what closes it)

| Blind spot | Evidence | Closes it |
|---|---|---|
| Files written by **Bash** (derived data, `sed -i`, redirects) | T1: `trace_claude.py` dead-ends at `notes/derived.txt` and at the `Alicia` edit [RUN] | Vacant hook: workspace hash at Pre/Post of each Bash call (T7 attributes `notes/derived.txt` to `toolu_main_2_0` and `report.md`/`brief_request.md` to `toolu_main_10_0`) [RUN]. Content is not captured, only a hash, unless the hook stores blobs. |
| **Background Bash** (`run_in_background:true`) | `notes/late.txt` is in the SessionEnd snapshot but no step claims it [RUN] | Enclosure/FS-level audit (fanotify, overlay), or deny `run_in_background` via PreToolUse `updatedInput` or deny [INF] |
| **Validation-rejected tool calls** | Edit no-match: no PreToolUse, no PostToolUseFailure [RUN] | The transcript `is_error` `<tool_use_error>` result |
| **Permission denials** | Only PreToolUse and `PermissionRequest` (no `tool_use_id`) [RUN] | Result `permission_denials[]`, transcript, OTel `tool_decision{decision,source}` |
| **Side-model calls** (WebFetch summarizer) and the **raw page** | Not in transcript, hooks or stream-json. Only proxy body `004.json` / `014.json` (`"Web page content:\n---\nCity Hall…Mayor: Bob Stone…"`) and OTel `api_request_body{query_source:"web_fetch_apply"}` [RUN] | Proxy (full), or OTel (bodies ≤ 61439 chars) |
| **Exact model output** | Hooks and transcript store normalized input (`replace_all` injected) [RUN] | Proxy raw SSE |
| **Full context of a model turn** | The transcript reconstructs it, but `prompt_snapshot` only records the system prompt at changes. OTel request bodies are truncated at 61439 chars [RUN] | Proxy request body |
| **Sub-agent structured results** | Missing `toolUseResult` in the sub-agent transcript [RUN] | PostToolUse hook payload |
| **Thinking / rationale** | Transcript only (with a real API, thinking may be redacted or signature-only [INF]) | Transcript, proxy |
| **Who changed a watched file** | FileChanged has no `tool_use_id` or `agent_id`, and is delayed and coalesced [RUN] | Per-call snapshots |
| **External effects via MCP** | Visible as `tool_input` (`send_email` body `"Population: 3072"`) and `tool_response` [RUN], but the effect itself cannot be undone | Gate at PreToolUse (deny or defer; see the earlier sheet) or a recipient-side check |
| **Tamper-resistance** | The transcript is plain JSONL in `$HOME`, flushed asynchronously, swept after 30 days [RUN]; the agent could rewrite it [INF] | Hash every hook record into Vacant's signed chain synchronously; at SessionEnd hash and copy the transcript files |
| **Network or process effects inside Bash** (curl, git push) | Not in any payload beyond the command text [INF, consistent with the earlier sheet] | Enclosure (netns) or proxy |

---

## 6. Trace-back demo: `trace_claude.py` [RUN]

This is the output of the same generic walk on three runs. `$OUT` is abbreviated.

**T7_full** (hook workspace snapshots on). The run makes both errors: an agent bug and a silent Bash edit.

```
CHECK C1 population: report=3072 source=30720 -> FAIL
- '3072' entered report.md at toolu_main_5_0 Write actor=main(main-thread) msg=msg_main_5_11 model=srv:claude-opus-5-5 request=req_mock_011 via Write
  <- the actor had read '3072' earlier from toolu_main_4_0 Read actor=main(main-thread) msg=msg_main_4_10 …
    - '3072' entered notes/derived.txt at toolu_main_2_0 Bash actor=main(main-thread) msg=msg_main_2_8 model=srv:claude-opus-5-5 request=req_mock_008 via Bash (fs-diff, content not in any payload)
      token not in the step input text => produced by executing the step's own command
      verdict: AGENT_ERROR — correct reference '30720' was visible to the actor at toolu_main_0_1 before this step
CHECK C2 mayor: report='Alicia Chen' page='Alice Chen' -> FAIL
- 'Alicia' entered report.md at toolu_main_10_0 Bash actor=main(main-thread) msg=msg_main_10_17 … via Bash (fs-diff, content not in any payload)
  verdict: AGENT_ERROR — correct reference 'Alice Chen' was visible to the actor at toolu_main_1_0, toolu_main_4_1, toolu_main_8_0 before this step
CHECK C3 external effect mcp__mail__send_email {'to': 'mayor@springfield.example', 'subject': 'Brief', 'body': 'Population: 3072'} -> FAIL  (toolu_main_9_0 … request=req_mock_016)
UNATTRIBUTED files changed during the session (no step claims them): ['notes/late.txt']
```

**T9_badsrc**. The web page itself says "Bob Stone"; the reference truth is "Alice Chen".

```
- 'Bob' entered report.md at toolu_main_4_0 Write actor=main(main-thread) msg=msg_main_4_10 …
  <- the actor had read 'Bob' earlier from toolu_main_1_0 Agent actor=main(main-thread) msg=msg_main_1_2 …
    hand-off: toolu_main_1_0 delegated to sub-agent ab7323f1d079d49fe (3 steps); its report carried the token
    <- inside the sub-agent the token first arrived as the result of toolu_sub_0_0 WebFetch actor=ab7323f1d079d49fe(general-purpose) msg=msg_sub_0_3 …
      external input: WebFetch result is a SIDE-MODEL summary (url=https://127.0.0.1:44957/mayor.html); the raw page and the side-model call are NOT in the transcript
      verdict: INPUT_ERROR candidate — … reference 'Alice Chen' was never visible to it (page vs side-model split needs the proxy body or OTel …)
```

**T1** has no snapshots. The walk stops at `! no recorded step introduced '3072' into notes/derived.txt`, and at the same message for `'Alicia'` in `report.md`. This is the measured cost of relying only on hooks and transcripts.

Pitfall found while building it [RUN]: naive substring provenance matched `3072` inside `30720` and blamed the Read of the correct CSV. The tracer uses word-boundary matching. A production tracer needs typed extraction, not string search [INF].

---

## 7. Recommended capture recipe (Claude Code adapter)

1. **One `--settings` file** (the only reliable additive injection; see `understand/agent-claude.md` §2). It contains:
   - `"disableAllHooks": false`;
   - command hooks with `timeout` on: `SessionStart`, `UserPromptSubmit`, `PreToolUse`, `PostToolUse`, `PostToolUseFailure`, `PostToolBatch`, `PermissionRequest`, `SubagentStart`, `SubagentStop`, `Stop`, `SessionEnd` (plus `ConfigChange` as a tamper guard);
   - no matcher, so every tool is covered, including MCP.

   Hooks run synchronously, so each hook appends to Vacant's signed hash chain before the next model call. Each record holds `session_id`, `prompt_id`, `actor` = `agent_id` or `main`, `agent_type`, `tool_use_id`, `tool_name`, and `sha256(tool_input)` / `sha256(tool_response|error)` (store blobs content-addressed).
2. **Per mutating call, workspace hashes**: take them at `PreToolUse` and `PostToolUse` for Bash, and for any non-read-only tool. Record the diff as the call's `writes[]`. Mark bg Bash and any session-level diff no call claims as `unattributed`. Optionally rewrite `run_in_background:true` to false, or deny it, via PreToolUse.
3. **Lineage**: at `SubagentStart` record `agent_id`. The parent link comes later from `…/subagents/agent-<id>.meta.json` (`toolUseId`, `parentAgentId`, `spawnDepth`), or live from stream-json `task_started`.
4. **Model turn join (post hoc)**: at `SessionEnd` the transcript was complete in 6/6 runs. Then:
   - ingest the main file, `subagents/*.jsonl` and `*.meta.json`;
   - hash each file into the chain;
   - copy it out, because of the 30-day sweep and because it is agent-writable;
   - join by `tool_use_id` to get `message.id`, `message.model` (served), `requestId`, and the thinking or text blocks of the same `message.id`.

   Rebuild each turn's context by `message.id` plus `sourceToolAssistantUUID`, not by the `parentUuid` walk.
5. **Optional proxy** (`ANTHROPIC_BASE_URL`): capture the requested model, the full context, the raw tool-input bytes and the side calls, keyed by `x-claude-code-session-id`, `x-claude-code-agent-id` and `x-claude-code-parent-agent-id`, plus the response `request-id` and `message.id`.
6. **Optional OTel**: `CLAUDE_CODE_ENABLE_TELEMETRY=1`, OTLP http/json to a local Vacant sink, `OTEL_LOG_TOOL_DETAILS=1`, `OTEL_LOG_RAW_API_BODIES=1`. It is the cheapest way to see side calls (`query_source:"web_fetch_apply"`) and `tool_decision.source` without a proxy. Bodies are truncated at 61439 chars.
7. **Blame**: when a check fails, run the generic walk (§6):
   1. find the introducing write;
   2. find that actor's earlier inputs carrying the value;
   3. recurse Read → writer, Agent → sub-agent, WebFetch → external input;
   4. classify by whether the reference was visible to the actor, which separates AGENT_ERROR from INPUT_ERROR candidate;
   5. emit the `(actor, agent_type, model, message.id, requestId, tool_use_id)` tuple for `reputation.py` keys and `router.py`.

---

## 8. Gaps and what was not verified

- Only `claude -p` (headless) was run. Interactive TUI sessions, `--resume`/`--continue`, `/compact` (whether pre-compaction records stay in the file), `--worktree`/`isolation:"worktree"` sub-agents, agent teams (`SendMessage`, `TeammateIdle`, `TaskCreated`) and `SubagentHandback` were not exercised.
- With a mock upstream there is no real thinking redaction, no server tools (WebSearch runs upstream), no `stop_reason` variety, and no real `request-id` format. Real-API field fidelity is [INF].
- `PostToolBatch` for bg sub-agents, and hook behavior when two sub-agents run truly concurrently with overlapping Bash writes, were not measured. Cross-actor diff ambiguity is [INF].
- FileChanged was only partly characterized: delayed and coalesced, and silent for watch paths under a missing directory. The exact trigger timing is unknown.
- OTel was run once. Whether `tool_result` events ever carry an agent attribute in other paths was not checked. Metric and trace exporters were off.
- Hook overhead at scale (Python startup about 30–70 ms per event), and the SessionEnd 1.5 s default budget with large transcripts, were not load-tested.
- Transcript tampering by the agent was not demonstrated (it is [INF]).
- `--bare` kills all hooks, and hooks are fail-open. That comes from the earlier sheet `understand/agent-claude.md` and was not re-measured here.
