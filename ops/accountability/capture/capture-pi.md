# pi 0.87.1: capturing the trajectory for accountability

Date: 2026-09-24. Binary: `scratchpad/agents/node_modules/.bin/pi` → `@earendil-works/pi-coding-agent/dist/bundle/cli.js`; `pi --version` prints `0.87.1` [RUN].

This sheet answers one question. A person drives **one** pi session on a general task (the lab task is a board memo, not code). Can Vacant do the following?

1. Record **who did what** as it happens: every tool call, what it read, what it wrote, which model turn issued it, and which agent or sub-agent took the step.
2. When a check on the deliverable fails, **trace back** to the step that caused it.
3. Tell "the input or requirement was wrong" apart from "the agent got it wrong".

Constraints:
- Nothing under `/home/user/Vacant` was modified.
- No real key was used and no real model was contacted. Every run used `env -i`, an isolated `HOME` and `PI_CODING_AGENT_DIR`, `PI_OFFLINE=1`, `apiKey: "sk-fake-offline-000"` and a local scripted mock.
- `/home/user/Vacant/.venv/bin/python` was used only to run the ed25519 verifier, because the system `python3` has a broken `cryptography`.

## Evidence tags

- **[RUN]**: I executed it and saw the result. Run names refer to `LAB/runs/<name>/`.
- **[SRC]**: I read it in the installed JS or `.d.ts`: `PI/dist/core/extensions/types.d.ts`, `AC/agent-loop.js`, `PI/dist/core/agent-session.js`, `PI/dist/core/session-manager.js`, `AI/api/*.js`.
- **[DOC]**: from the bundled `PI/docs/*.md` or `PI/examples/**`.
- **[INF]**: my inference, not verified.

Paths:
- `PI` = `scratchpad/agents/node_modules/@earendil-works/pi-coding-agent`
- `AC` = `PI/node_modules/@earendil-works/pi-agent-core/dist`
- `AI` = `PI/node_modules/@earendil-works/pi-ai/dist`
- `LAB` = `scratchpad/accountability/pi`

## Lab (`LAB/`)

| File | Role |
|---|---|
| `mock_pi.py` | Scripted OpenAI Chat Completions SSE upstream, derived from `ops/intake/mock_model.py`. It picks a script by the route whose `match` substring appears in the latest user message, so the sub-agent's `Task: …` gets its own script. Step `k` is the number of `role:"tool"` messages after that user message. A step can emit `reasoning_content` (thinking), text, or **several tool calls at once** (a parallel batch). It serves static "web" files on GET (`/feed/fx.json`). Responses carry the header `x-request-id: mockreq-<n>` and chunk `id: chatcmpl-<n>`, and they report `model: "<requested>-served"`, so the requested and served models can be told apart. Each request body is dumped to `mock/req_<n>.json`. |
| `ext/vacant-trace.ts` | **Probe tracer extension.** It records every trajectory event into a **per-process signed hash chain**, `trace/trace-<pid>.jsonl`. Each line is `{seq, prev, h, sig, body}`, with `h = sha256(prev+"\n"+body)` and `sig = ed25519(h)`. The public key is in the `genesis` record. The tracer also records: a per-tool-call workspace delta (sha256 of the files in cwd); `leafIdAtCall`; and a parent→child link, env `VACANT_PARENT_LINK`, which is set when the parent dispatches `subagent`. |
| `ext/subagent/{index,agents}.ts` | An unmodified copy of pi's **shipped example** sub-agent extension (`PI/examples/extensions/subagent`). |
| `ext/mutate.ts`, `ext/mutate2.ts` | Adversarial co-resident extensions. `mutate.ts` rewrites executed `write` args and a finalized assistant message. `mutate2.ts` rewrites a bash tool **result**. |
| `run_pi.py <run> <e_only\|global\|none> [--scenario …] [--mode json\|print] [--extra ext.ts] [--kill-after s --kill-sig SIG]` | Drives the real pi against the mock. `e_only` loads the tracer via `-e` (first in load order). `global` drops it in `<agentDir>/extensions/`, where it loads last and is inherited by child pi processes. |
| `rpc_probe.py` | RPC mode: a human `bash`, two prompts, `set_model` mid-session, `fork`, then a third prompt. |
| `verify_chain.py` | Checks prev linkage, hashes and signatures (`--tamper N` flips one record). |
| `trace_pi.py <run> [--session-only]` | Reconstructs the trajectory and runs the trace-back for failed checks (§6). |

**Scenario `memo`** (general task). The prompt is "Prepare the Q3 board memo as described in brief.md". The main agent does the following:
1. `read brief.md` and `read data/q3.csv` in parallel, in one assistant message with a thinking block.
2. `bash curl -s http://127.0.0.1:<port>/feed/fx.json`, a "web" input that returns `usd_eur: 0.95`. The official rate is 0.92.
3. `subagent {agent:"risk-checker", task:"Count the CRITICAL risks …"}`. A child pi process reads `data/risks.txt` (which lists 2 CRITICAL risks) and writes `notes/risks.md` = "**3** critical risks …".
4. `read notes/risks.md`.
5. `write memo.md` with `USD 1234` (the CSV sums to **1243**), `0.95`, and "3 critical risks".
6. `bash printf 'Sign-off: pending\n' >> memo.md`.

Three deliverable checks fail, each for a different reason:
- **C1** total: the agent's own error.
- **C2** rate: an external input error.
- **C3** risk count: the sub-agent's error.

Other scenarios:
- `req`: the brief itself says "use 0.95", and the delegation task text carries "3 critical risks".
- `parallel_sub`: 3 children at once.
- `fail`: invalid, unknown and failing tool calls.
- `edit`: exercises the edit tool.
- `bashpi`: nested pi launched through bash.
- `slow`: used with a kill mid-tool.

All runs exited 0 except the kill runs, and each took about 1.4–2.3 s wall [RUN].

---

## 0. Decision-relevant summary

1. **One provider-issued key joins every channel: `toolCallId`** [RUN]. It is the model's `tool_calls[].id` (here `call_<n>_<i>`). It appears in:
   - the assistant `toolCall` block `{type:"toolCall", id, name, arguments}`;
   - `tool_execution_start`, `tool_call`, `tool_execution_update`, `tool_result` and `tool_execution_end`;
   - the `toolResult` message `{role:"toolResult", toolCallId, toolName, content, details?, isError}`;
   - the JSON stdout stream;
   - the session file.

   pi does not mint its own step id. Uniqueness therefore depends on the provider [INF].
2. **The model turn behind each step is directly available**, both in-process and in the session file [RUN]. The assistant message carries:
   - `api`, `provider`, `model` (requested), **`responseModel`** (served: `"mock-model-served"`), **`responseId`** (provider id: `"chatcmpl-8"`), `usage`, `stopReason`, `rawStopReason` and `timestamp` (request start, ms);
   - `thinking` blocks.

   `after_provider_response.headers` has the provider request id (`x-request-id: "mockreq-1"`). `ctx.model` = `{provider,id,api,baseUrl,…}`.
3. **Live, the issuing assistant entry id is known at `tool_call` time** [RUN, 7/7]. `ctx.sessionManager.getLeafId()` inside the `tool_call` handler equals the persisted assistant entry id, including for parallel calls.

   `turn_end` gives `messageEntryId` and `toolResultEntryIds[]` [RUN]. `message_end` fires **before** its entry is persisted: at that moment `getLeafId()` is the entry's **parent** [SRC `agent-session.js:580-595`; RUN].
4. **The native session file alone supports reconstruction and trace-back** [RUN, `trace_pi.py --session-only`]:
   - The file is a `parentId` tree of JSONL entries.
   - Each message is appended with `appendFileSync` at `message_end`, so the file is live, but it is only created once the first assistant message exists.
   - It holds the system prompt sections, user prompts, assistant turns (model, responseId, thinking, toolCall args) and tool results (content, `isError`, `details`; for edit: a unified `patch`).
   - Human `bash` is recorded as `role:"bashExecution"`.
   - All three verdicts (C1–C3) came out right from the session file alone.
5. **Sub-agents: pi has none built in** [SRC: built-in tools are `read, bash, powershell, edit, write, grep, find, ls`; the default active set is `read, bash, edit, write`]. Delegation comes from extensions. The **shipped example** `subagent` spawns `pi --mode json -p --no-session --model <provider/id> --tools … --append-system-prompt <tmp> "Task: …"` [RUN argv]. Consequences:
   - The child writes **no session file**.
   - The child's full transcript (system sections incl. `addendum`, task, assistant turns with their own `toolCallId`s, `responseId`s and results) is **embedded in the parent's persisted `subagent` toolResult `details.results[].messages`** [RUN].
   - `-e` does not reach the child. A tracer dropped in `<agentDir>/extensions/` does [RUN: `e_only` gives 1 trace file, `global` gives 2].
6. **Linking a child process to the parent step** [RUN `p1`]:
   - The env link set in `tool_call` was **wrong for 2 of 3 children**. In a parallel batch, every `tool_call` handler runs before any execution [SRC `agent-loop.js:406-452`], so all children inherited the last call's id.
   - The **content join** was correct 3/3. The child's own `toolCallId`s (from its trace) match the ids inside the parent's `details.results[i].messages`.
   - `ppid` = parent pid [RUN].
7. **Parallel execution breaks workspace-diff attribution** [RUN `p1`]:
   - Default tool execution is **parallel** (`toolExecution ?? "parallel"`, and pi exposes no setting) [SRC `AC/agent.js:143`].
   - Parent `call_1_0` was credited with 3 files, one of them written by `call_1_1`'s child. `call_1_1` was credited with 0.
   - Child 12014's `read` was credited with `notes/title.md`, which its sibling wrote.
   - Diffs are exact only for sequential, single-process steps.
   - `write`/`edit` do not need diffs, because their args and `details.patch` say what was written. `bash` and custom tools do.
8. **Some calls never reach `tool_call`/`tool_result`** [RUN `f1`]:
   - Schema-validation failures (`Validation failed for tool "edit"`) and unknown tools (`Tool websearch not found`) produce **only** `tool_execution_start`/`tool_execution_end{isError:true}` and a session `toolResult`.
   - Blocked calls behave the same way [SRC `agent-loop.js:398-411`].
   - Execution errors (ENOENT, edit no-match) do fire `tool_result{isError:true}`.
   - ⇒ Record `tool_execution_*`, not only `tool_call`/`tool_result`.
9. **A co-resident extension can make the record disagree with reality, and pi does not say which extension did it** [RUN]:
   - `m1`: a later `tool_call` handler changed `write` content from `USD 1234` to `USD 9999`. The session's `toolCall.arguments` still say `1234`, the file says `9999`, and only `tool_result.input` shows the executed args.
   - `m1`: a `message_end` handler returned a replacement. The session file and JSON stdout persisted `"REWRITTEN BY EXTENSION"`, while a first-position tracer saw the model's `"Memo written to memo.md."`.
   - `m2`: an earlier `tool_result` handler rewrote the curl output from 0.95 to 0.92. The session file and a **last-position** tracer (global drop) saw only 0.92. The real output existed only in the mock's log.
   - ⇒ Load the tracer **first** (`-e`) and diff it against the session file. Load order is `-e` → project → user-global [earlier sheet, RUN].
10. **The trace-back works end to end** [RUN, `trace_pi.py`, §6]:
    - C1 → `call_8_0` (main, `chatcmpl-8`): **ORIGINATED_BY_ACTOR**.
    - C2 → value in `bash curl` output: **external input error**. In `req` it traces to pre-existing `brief.md`: **requirement error**.
    - C3 → `read notes/risks.md` → written by sub-agent `call_5_0` (pid 12607, `chatcmpl-5`): **sub-agent error**. In `req`, the value was in the sub-agent's task, so it traces to the **delegating** main agent's `subagent` call.
    - `m1` C1: **MUTATED_AFTER_MODEL**. Session-only mode dead-ends there with "no recorded step wrote this value".
11. **The signed chain is cheap and verifies** [RUN]:
    - 7 trace files verified OK. Flipping one byte in record 40 gives `hash-mismatch` at seq 40.
    - Size for the memo run: parent 130 records / 123 KB, child 55 / 41 KB.
    - The in-process sha256 of each `before_provider_request` payload matched the sha256 of the body the mock received (compact JSON) **7/7**. That hash is a join key to a proxy-side record.
12. **Unattributed effects remain** [RUN `k_*`]:
    - On SIGINT and SIGKILL the running bash child kept going and created `late.txt` after pi died. The session and trace show `tool_call` with no `tool_result`.
    - SIGTERM killed the child and fired `session_shutdown`.
    - Effects made inside bash (files outside cwd, network, reads) are never itemized.

---

## 1. Capture channels compared

| Channel | What it gives for accountability | When | Blind spots (measured) |
|---|---|---|---|
| **Extension events** (`pi.on(...)`, in-process, awaited) | Everything: model-issued args at `tool_call`, **executed args** at `tool_result.input`, raw tool output at `tool_result.content` (if first in chain), `toolCallId`, issuing entry id (`getLeafId()`), `turn_end` entry ids, provider request payload, response status+headers (`x-request-id`), `ctx.model`, `model_select`, `user_bash`, `input.source` | Live, synchronous to the loop | Order-dependent view (§5). Nothing inside bash. Validation-failed, unknown and blocked calls appear only in `tool_execution_*`. `-e` is not inherited by child processes. |
| **Session file** `<agentDir>/sessions/--<cwd>--/<ISO>_<sid>.jsonl` | Full conversation tree: system sections, prompts, assistant turns (model/responseModel/responseId/thinking/toolCall args), toolResults (+`details`: edit `patch`, sub-agent transcripts), `bashExecution` (human), `model_change`, `thinking_level_change`, `custom*`, `compaction`, `branch_summary` | Live (append per message) after the first assistant message | Model-issued args, not executed args. Final (post-extension) messages and results. No pid. No per-call timing in parallel batches (all toolResults share the batch-end timestamp). Agent-writable, unsigned. `model_change` can disagree with the actual serving model (§3.4). |
| **`--mode json` stdout** | `session` header line, then `agent_start`, `turn_start` (just `{type}`), `message_start/update/end`, `tool_execution_start/update/end`, `turn_end{message,toolResults}`, `agent_end{messages,willRetry}`, `agent_settled`, `auto_retry_*`, `compaction_*` | Live | No `tool_call`/`tool_result`, so no executed args. No provider events. No entry ids. **No per-event timestamps**. No pid or model except inside messages. Only the process's own stream; the child's stream is consumed by the subagent extension. |
| **RPC stdout** (`--mode rpc`) | Same events plus command `response`s. `get_state{sessionFile,sessionId,model,…}`, `get_entries{since}`, `get_tree` | Live | Same as json. No `session` header line [RUN]. |
| **Proxy** (Vacant's `wireproxy`, or `pi.registerProvider(name,{baseUrl})`) | The exact bytes sent (the final payload after all `before_provider_request` handlers) and the raw response stream | Live | No tool execution. Join via `responseId`/`x-request-id` or payload sha256 (matched 7/7 in-process vs received). |
| **Tracer workspace snapshots** (Vacant's own) | Which files a bash or custom tool changed | Live | Wrong under parallel tool calls and parallel sub-agent processes [RUN `p1`]. A human editing concurrently would be charged to the next tool call [INF]. Effects after pi dies are missed. |

---

## 2. Extension events: order, payloads, ids

### 2.1 Order [RUN `g1`/`g2` traces; SRC `AC/agent-loop.js:364-452`]

For one prompt:
```
session_start → input → before_agent_start → agent_start
turn_start{turnIndex:0}
  message_start/end (system)  message_start/end (user)        ← first turn only
  context → before_provider_headers → before_provider_request → after_provider_response
  message_start (assistant, stopReason:"pending", responseId already set)
  message_update × n   (assistantMessageEvent.type ∈ thinking_start|thinking_delta|thinking_end|
                        text_start|text_delta|text_end|toolcall_start|toolcall_delta|toolcall_end)
  message_end (assistant)
  [per call, in assistant order]  tool_execution_start → tool_call        ← ALL calls of the batch, before any runs
  [per call, completion order]    tool_execution_update* → tool_result → tool_execution_end
  message_start/end (toolResult) × n     ← after the whole batch, in assistant order
turn_end{turnIndex:0, messageEntryId, toolResultEntryIds}
turn_start{turnIndex:1} … 
agent_end → agent_before_settle → agent_settled → session_shutdown{reason:"quit"}
```
- `tool_execution_start` fires **before** `tool_call`.
- `turnIndex` **resets to 0 for each prompt** (agent run) [RUN `rpc1`: 0,1 | 0,1,2 | 0]. A global step key must be `(sessionId, entryId)`, not `turnIndex`.
- `-p` (print) and `--mode json` produce identical extension-event counts [RUN `pr1` vs `e1`].

### 2.2 Payloads a tracer needs (exact, from the `.d.ts` and observed)

```ts
session_start   {type, reason:"startup"|"reload"|"new"|"resume"|"fork", previousSessionFile?}
                // ctx.sessionManager: getSessionId() "01a0d465-…" (UUIDv7), getSessionFile(), getHeader(), getLeafId()
                // ctx.model {provider:"mock", id:"mock-model", api:"openai-completions", baseUrl, name, …}; ctx.mode "json"
input           {type, text, images?, source:"interactive"|"rpc"|"extension", streamingBehavior?:"steer"|"followUp"}
                // a -p prompt reports source "interactive" [RUN]
before_agent_start {type, prompt, images?, systemPrompt (readonly), systemPromptOptions (mutable)}
turn_start      {type, turnIndex, timestamp}
context         {type, messages}                       // no system messages; handlers may return {messages}
before_provider_headers {type, headers}                // observed {} (auth is not exposed) [RUN]
before_provider_request {type, payload}                // full body: model, messages, stream, stream_options, store,
                                                       // max_completion_tokens, tools (+ undefined prompt_cache_*)
after_provider_response {type, status, headers}        // e.g. {"x-request-id":"mockreq-1", "content-type":"text/event-stream", …}
message_update  {type, message, assistantMessageEvent:{type, contentIndex, delta?|content?|toolCall?, partial}}
message_end     {type, message}                        // may return {message} to REPLACE it (§5)
tool_execution_start {type, toolCallId, toolName, args}
tool_call       {type, toolCallId, toolName, input}    // input mutable; may return {block, reason, terminate}
tool_execution_update {type, toolCallId, toolName, args, partialResult:{content, details}}
tool_result     {type, toolCallId, toolName, input /*EXECUTED args*/, content, details, isError, usage?}
                // may return {content?, details?, isError?, usage?} (chained)
tool_execution_end {type, toolCallId, toolName, result:{content, details?}, isError}
turn_end        {type, turnIndex, message, toolResults, messageEntryId, toolResultEntryIds,
                 outcome:"completed"|"aborted"|"error", entries, continue,
                 context:{contextEntries, contextMessages, llmMessages, pendingMessages, canContinue}}
agent_end       {type, messages}
agent_before_settle {type, outcome, entries, continue, context}
agent_settled   {type}
model_select    {type, model, previousModel, source:"set"|"cycle"|"restore"}   // fired by RPC set_model [RUN]
user_bash       {type, command, excludeFromContext, cwd}   // fired for RPC `bash` too [RUN rpc1]
session_shutdown {type, reason:"quit"|"reload"|"new"|"resume"|"fork", targetSessionFile?}
```
Correction to the earlier sheet `understand/agent-pi.md`:
- `tool_execution_end` **does** carry `toolCallId` [SRC+RUN].
- RPC `bash` **does** fire `user_bash` [RUN].

The assistant message as observed (the `message_end` and session `message.message` shape) [RUN]:
```json
{"role":"assistant",
 "content":[{"type":"thinking","thinking":"Sum is 1234; rate from feed 0.95.","thinkingSignature":"reasoning_content"},
            {"type":"toolCall","id":"call_8_0","name":"write","arguments":{"path":"memo.md","content":"# Q3 Board Memo…"}}],
 "api":"openai-completions","provider":"mock","model":"mock-model","responseModel":"mock-model-served",
 "responseId":"chatcmpl-8","usage":{"input":108,"output":18,"cacheRead":0,"cacheWrite":0,"reasoning":0,"totalTokens":126,"cost":{…}},
 "stopReason":"toolUse","rawStopReason":"tool_calls","timestamp":1790269635609}
```
`ThinkingContent` can be `{redacted:true, thinkingSignature:<opaque>}` on providers that encrypt reasoning [SRC `AI/types.d.ts:247-255`]. The content is then not observable.

`responseId` comes from the provider [SRC]:
- `anthropic-messages`: `message.id`
- openai-completions and mistral: `chunk.id`
- openai-responses: `response.id`
- google: `chunk.responseId`

### 2.3 Joining ids [RUN]

| From | To | How |
|---|---|---|
| tool step | issuing model turn | `toolCallId` ∈ assistant `content[].toolCall.id`. Live: `getLeafId()` inside `tool_call` = assistant entry id (7/7) |
| model turn | provider record | `responseId` (in message); `x-request-id` (`after_provider_response`); sha256(payload) (`before_provider_request`) |
| event stream | session entries | `turn_end.messageEntryId` / `toolResultEntryIds[]`; `message_end` + `getLeafId()` = the parent of the entry about to be written |
| child process | parent step | content join: the child's `toolCallId`s ∈ parent `toolResult(subagent).details.results[i].messages` (3/3). Env var set in `tool_call`: 1/3 in a parallel batch. `ppid` |
| forked session | origin | header `parentSession: <path>`. Entry ids are **copied** into the fork (the same ids exist in both files), so the global key is `(sessionId, entryId)` [RUN `rpc1`] |

### 2.4 Model identity [RUN]

- Per turn: `message.provider/model` (requested), `responseModel` (served) and `responseId`.
- Per session: `ctx.model` (includes `baseUrl`), the session `model_change` entry and `model_select{source}`.
- Env given to bash-tool children: `PI_MODEL`, `PI_PROVIDER`, `PI_SESSION_ID` and `PI_SESSION_FILE` [RUN `bp1`]. These are **not** in the pi process's own `process.env` [RUN genesis `piEnv`], so they do not reach a child spawned by an extension.

---

## 3. The session file

### 3.1 Location and lifecycle [RUN; DOC `session-format.md`; SRC `session-manager.js:785-813`]

- Location: `$PI_CODING_AGENT_DIR/sessions/--<cwd, "/"→"-">--/<ISO-ts>_<sessionId>.jsonl`. Override it with `--session-dir` or `PI_CODING_AGENT_SESSION_DIR`. `--session-id <id>` makes the id deterministic, for example equal to a Vacant run id.
- `--no-session` means nothing is written, which is what the example sub-agent uses.
- The file is created only when the first assistant message exists. Earlier entries are buffered and then written in one go. After that, every entry is appended synchronously.
- A run killed before the first model response leaves **no file** [SRC].
- After SIGINT, SIGKILL and SIGTERM mid-tool, the file ended with the assistant entry that issued the in-flight call, and no `toolResult` [RUN `k_*`].

### 3.2 Record types seen [RUN]

- Header `{"type":"session","version":3,"id","timestamp","cwd"[, "parentSession"]}` (no `id`/`parentId`).
- Every other entry: `{type, id (8-hex), parentId, timestamp (ISO, persist time), …}`:
  - `model_change{provider, modelId}` and `thinking_level_change{thinkingLevel}`, at start and on change;
  - `message{message: system}`: `{role:"system", content:"", sections:{preamble,tools,rules,docs,[addendum],cwd}, toolsAdded:[{name,description,parameters}]}`. Later prompt or tool changes are patches: `sections` by name, `toolsAdded`/`toolsRemoved`;
  - `message{user}`, `message{assistant}` (§2.2), and `message{toolResult: {toolCallId, toolName, content, isError, details?, timestamp}}`;
  - `message{bashExecution: {command, output, exitCode, cancelled, truncated, timestamp}}`. This is a **human** shell command (RPC `bash` / TUI `!`). It has no `toolCallId`, so it can be told apart from agent steps [RUN `rpc1`].
- Documented but not produced here: `custom{customType,data}` (from `pi.appendEntry`, not sent to the LLM), `custom_message`, `compaction{summary, firstKeptEntryId, systemMessage, details:{readFiles, modifiedFiles}}`, `context_edit{targetId, replacement}`, `branch_summary{fromId, summary, details:{readFiles,modifiedFiles}}`, `label`, `session_info`, `usage` [DOC].
- Compaction and `context_edit` change only what the **model** sees next. Raw entries stay in the file [DOC]. A reconstruction therefore sees everything, but "what the model saw at turn t" must be recomputed (`buildSessionProjection`) or taken from `before_provider_request`.
- Persisted `details` [RUN]:
  - edit: `{diff, patch:"--- memo.md\n+++ memo.md\n@@ -1,2 +1,2 @@\n-Total: 1243\n+Total: 1234\n …", firstChangedLine}` (`ed1`);
  - subagent: `{mode, agentScope, projectAgentsDir, results:[{agent, agentSource, task, exitCode, messages[…full child transcript…], stderr, usage, model:"mock/mock-model", stopReason, step?}]}`;
  - write: `null`;
  - bash: `{truncation, fullOutputPath}` only when truncated [SRC].

### 3.3 Tree and branches [RUN `rpc1`; DOC]

- In-place branches are siblings under the same `parentId` in one file, created by `/tree` navigation. `branch_summary` marks an abandoned path.
- RPC `fork{entryId}` (or `/fork`, `/clone`, and the handoff example's `newSession({parentSession})`) creates a **new file** whose header has `parentSession`. It copies the path up to the fork point **with the same entry ids**.
- The fork also re-invokes the extension factory in the same pid: a second `genesis` appears, and `session_start{reason:"fork"}` fired **twice**. The tracer's module state (key, seq, prev) survived because jiti caches the module [RUN]. Handlers should be idempotent and key their state by session id.

### 3.4 Caveat: `model_change` is not authoritative [RUN `rpc1`]

The forked file's path contains `model_change → mock-model-b`, but the next assistant turn (mock request 6) was served by `mock-model`, and `get_state` after the fork reported `mock-model`. **Attribute from each assistant message's `provider/model/responseModel`**, not from `model_change`.

### 3.5 Reconstructing after the fact (what `trace_pi.py` does) [RUN]

1. Parse the header, then entries. Take the path root→leaf (or all branches).
2. Build `toolCallId → {assistant entry id, provider/model/responseModel/responseId, thinking, arguments}` and `toolCallId → {toolResult entry id, content, isError, details}`.
3. For each actor, walk its messages in order. The inputs visible before step *s* are the user/delegation prompt plus every earlier toolResult's content.
4. For each `subagent` toolResult, add a child actor from `details.results[i].messages`: actor = `subagent:<agent>#i`, `parent_toolCallId`, declared model.
5. Optionally merge the tracer chains: executed args, fsDelta, pid, the child's in-memory session id, and chain verification.

---

## 4. Sub-agents and delegation

- **Native: none.** There is no Task-like tool in `allToolNames` [SRC `PI/dist/core/tools/index.js:19-24`].
- Delegation exists only through extensions or process nesting.

| Mechanism | What pi records | Link to the parent step | Measured |
|---|---|---|---|
| **Example `subagent` extension** (`PI/examples/extensions/subagent`: single / parallel with up to 8 tasks and 4 concurrent / chain) | Parent session: `toolCall{name:"subagent", arguments:{agent,task}\|{tasks[]}\|{chain[]}}` plus `toolResult.details.results[]` with the **full child transcript**. Child: `--no-session`, so no file | The parent `toolCallId` owns `details.results[i]`. The child's own ids appear inside it | [RUN `g2`, `p1`] |
| **Nested `pi` via the bash tool** | The child writes **its own session file** in the same sessions dir, with **no `parentSession`**. The parent sees only stdout text | The child's env has `PI_SESSION_ID`/`PI_SESSION_FILE` of the parent (bash-tool env), and `ppid` = the bash shell. **No toolCallId**. Time bracketing against the parent's in-flight bash call | [RUN `bp1`] |
| **Fork / clone / handoff** (new session from an old one) | New file with `parentSession` header | Session-level lineage only | [RUN `rpc1`; DOC handoff example] |
| Third-party sub-agent packages, and ACP (`pi-acp` spawns `pi --mode rpc`) | Unknown; depends on the package | — | not verified |

Tracer coverage:
- `-e` does not propagate to children [RUN `e1`: 1 trace for 2 processes].
- A drop in `<agentDir>/extensions/` does [RUN `g2`: 2 traces; `p1`: 4].
- The child's `argv` shows its constraints: `--tools read,write`, `--model mock/mock-model`, `--thinking off` and the task [RUN].
- Its system `sections.addendum` (the agent definition's prompt) is in `details` [RUN]. So the **instructions each actor received** are on record, which is what the requirement-vs-agent judgement needs.

The child's in-memory session id exists (the tracer logged `01a0d462-bafd-…`) but is not in the parent record [RUN].

---

## 5. Integrity: where the record can diverge from reality

In-process, every mutating hook is a chain. A later handler sees and can change the earlier handler's output, and pi records no per-extension attribution [SRC `types.d.ts`; RUN].

| Hook | Effect of a later/earlier extension | What diverges | Measured |
|---|---|---|---|
| `tool_call` (`input` mutable in place) | Executed args ≠ model-issued args | Session `toolCall.arguments` = model's. The file on disk = mutated. Only `tool_result.input` shows the executed args | [RUN `m1`: 1234 vs 9999] |
| `tool_result` (returns replacement) | The model and the session see a rewritten result | The raw tool output is visible only to a tracer **earlier** in the chain | [RUN `m2`: the global tracer saw 0.92; the feed returned 0.95] |
| `message_end` (returns `{message}`) | The persisted assistant message ≠ what the model produced | Session + JSON stdout = rewritten; a first-position tracer = original | [RUN `m1`] |
| `context`, `context_with_system`, `before_provider_request`, `input`, `before_agent_start` | What the model actually saw ≠ the session context | Ground truth = the final payload (the last handler or the proxy) | [SRC] |

Also:
- The session file and the tracer's own files are writable by the agent's `bash`/`write` [INF].
- The tracer's signing key lives in the pi process, so a co-resident extension can forge records [INF].
- **Honest boundary:** the in-process chain proves only that records were not edited after being written by a key-holder. For custody, stream the records out-of-process to a Vacant recorder that signs with its own key [INF].

Verification [RUN]:
- `verify_chain.py` passed on all 7 chains (`g2`, `p1`×4, `rpc1`). `--tamper 40` gives `[[40,"hash-mismatch"]]`.
- The child chain's genesis carries the parent's chain head at dispatch (`parentLink.traceHead`), which anchors cross-process order. It inherits the env race in §0.6.

---

## 6. Trace-back demo: `trace_pi.py` [RUN]

Method:
1. Each check extracts the offending value from the deliverable and a **provenance token** (`1234`, `0.95`, `3 critical risks`).
2. Find the last step that wrote that token into the file (write/edit args, or a bash command plus fsDelta).
3. Look for the token in the inputs that actor had seen before that step. Priority: its prompt/task, then read results, then sub-agent output, then bash output.
4. Recurse into `read` files: find who wrote them in-session. If nobody did, the file was pre-existing (owner-supplied). For a prompt hit inside a sub-agent, recurse into the parent step that issued the delegation.

| Run | Check | Chain (writer ← source) | Verdict |
|---|---|---|---|
| `g2` | C1 `1234` | `write memo.md` `call_8_0`: main, pid 12590, `chatcmpl-8`, entry `bc096c78`, thinking "Sum is 1234" | **ORIGINATED_BY_ACTOR** (agent error) |
| `g2` | C2 `0.95` | `call_8_0` ← `bash curl …/feed/fx.json` `call_2_0` | **COPIED_FROM_COMMAND_OUTPUT → external input error** |
| `g2` | C3 `3 critical risks` | `call_8_0` ← `read notes/risks.md` `call_7_0` ← `write` `call_5_0` by `subagent:risk-checker#0` (pid 12607, `chatcmpl-5`, parent `call_3_0`), whose only input `data/risks.txt` lacks it | **sub-agent ORIGINATED** |
| `rq1` | C2 | `call_8_0` ← `read brief.md` ← no in-session writer | **FROM_PRE_EXISTING_INPUT brief.md → requirement error** |
| `rq1` | C3 | … ← sub-agent `call_5_0` ← its **task** ← parent `subagent` call `call_3_0` (main, `chatcmpl-3`) | **FROM_DELEGATION_TASK → delegator (main) originated** |
| `m1` | C1 `9999` | `call_8_0`: executed args ≠ model args | **MUTATED_AFTER_MODEL** (co-resident extension, not the model) |
| `m1 --session-only` | C1 | none | "PRE_EXISTING_OR_UNRECORDED", a dead end |
| `g2 --session-only` | C1–C3 | same as `g2` without pids | same verdicts |

Every node cites the evidence needed to re-verify it:
- session file sha256 + entry ids;
- trace file + `seq` + `h`;
- `responseId`.

The output is `runs/<run>/traceback.json`.

Limits [INF]:
- Co-occurrence shows that the value was **present** in an input, not that it was **derived** from it.
- Computed values such as `EUR 1172.30 = 1234 × 0.95` need derivation reasoning or re-computation by the checker.
- Tokens that are too short (`3`) are meaningless. The check spec must name a distinctive token.
- "Inputs seen" = session order. If `context` handlers or compaction removed messages, use the turn's `before_provider_request` payload instead.

---

## 7. What is NOT observable in pi (and what would close it)

| Gap | Evidence | Closure |
|---|---|---|
| What a `bash` command itself read, wrote (outside cwd) or sent over the network | Only `command` + text output. Reads are never visible [SRC] | OS-level tracing, or a sandbox with a per-process overlay/netns (`vrun/sandbox.py`) |
| Per-call file effects under parallel tool calls or parallel sub-agents sharing a cwd | `p1` mis-attribution [RUN] | Per-call overlay or fanotify with pid. Or force sequential by overriding tools with `executionMode:"sequential"` [SRC `agent-loop.js:366`; not run]. A second override of the same tool name makes pi exit 1 (earlier sheet) |
| Raw model output bytes; redacted/encrypted thinking | Only the parsed `AssistantMessage` [SRC] | Proxy |
| Which extension mutated args, results, messages or context | Not attributed by pi [SRC] | First-position tracer + session diff detects *that* something changed, not *who* |
| Sub-agent trajectory when the delegation extension does not expose it | The example embeds it in `details`; others may not | A tracer dropped into the agent dir (inherited by children) + content join |
| Parent `toolCallId` for nested pi via bash | Only `PI_SESSION_ID` [RUN `bp1`] | Time bracketing against the in-flight bash call; argv match |
| Effects after pi dies (SIGINT/SIGKILL orphans) | `late.txt` [RUN] | A post-exit workspace diff by the launcher, charged to the unmatched `tool_call` |
| Runs killed before the first model response | No session file [SRC] | The tracer chain (it starts at `genesis`) |
| Human edits made outside pi during the session | Never recorded. Tracer snapshots would **misattribute** them to the next tool call [INF] | A filesystem watcher that sees pid/uid |
| Per-call timing inside a parallel batch | Session toolResult timestamps = batch end (the same ms in `g1`) [RUN] | Tracer `t` at `tool_call`/`tool_result` |
| `model_change` truth after a fork | §3.4 [RUN] | Per-message `provider/model/responseModel` |

---

## 8. Recommended capture recipe (pi adapter)

1. **Use one tracer file, at two load positions.**
   - Put it at `<agentDir>/extensions/vacant-trace.ts`, dormant unless `VACANT_RUN_ID` is set. Child pi processes (sub-agents, nested pi) auto-load it from there, so they are traced too [RUN `g2`/`bp1`].
   - When Vacant launches the parent, also pass `-e` with that **same path**. pi deduplicates by canonical path [earlier sheet RUN], and the CLI copy sorts first, so the parent's single instance should load **first** [INF on which slot wins]. First position sees model-issued args, the raw tool output and the original assistant message.
   - A *different* file at each location would load twice and double-log [INF].
   - Presence must be proven per run, because a settings exclusion can silently disable the drop (earlier sheet).
2. **Record these events:**
   - lifecycle: `session_start`, `input`, `before_agent_start` (sha256 of the system prompt), `model_select`, `turn_start`/`turn_end` (entry ids), `agent_settled`, `session_shutdown`, `user_bash`;
   - provider: `before_provider_request` (sha256 of the payload) and `after_provider_response` (status, request-id header);
   - `message_end` (full assistant message);
   - `tool_execution_start`, `tool_call` (with `getLeafId()`), `tool_result` (executed `input`, content, details) and `tool_execution_end`.
3. **Stream the records out-of-process** to the Vacant recorder (pipe or socket), which hash-chains and signs with its own key.
   - Key the records by `(sessionId, entryId, toolCallId, pid)`.
   - Setting `--session-id <vacant-run-id>` makes the join trivial.
4. **After the child exits, the launcher must:**
   - copy and hash the session file;
   - diff it against the first-position tracer (message, args and result divergence ⇒ flag a co-resident extension);
   - take a workspace diff and charge unexplained changes to any unmatched `tool_call`.
5. **Link sub-agents by content join**, not by env: the child's `toolCallId`s ∈ the parent's `details.results[].messages`. Fall back to `ppid` + argv task text, or `PI_SESSION_ID` + time for nested pi.
6. **Reputation keys** [INF], mapped to `reputation.py`'s `(stream, branch, substrate)`:
   - stream = the agent identity (main session / the sub-agent definition `agent` + `agentSource`);
   - branch = the delegation path (`parent_toolCallId` chain);
   - substrate = `provider/responseModel`.
   - Only verdicts **ORIGINATED_BY_ACTOR** and **FROM_DELEGATION_TASK** (charged to the delegator) should move an agent's reputation. **External-input** and **requirement** verdicts go to the source or owner, and **MUTATED_AFTER_MODEL** goes to the extension set, not the model.

---

## 9. Gaps and what was not verified

- Only the `openai-completions` wire was driven in these runs. The `responseId` sources for the other APIs are [SRC] only.
- Compaction, `context_edit`, `/tree` in-place branching, steer/follow-up mid-run, and `session_before_*` cancellation were not exercised in this lens [DOC only].
- Forcing sequential execution via `executionMode:"sequential"` overrides was not run.
- Third-party sub-agent packages, `pi-mcp-adapter` tools (they would appear as custom tool calls) and `pi-acp` were not tested.
- Tool-call id uniqueness across processes with real providers is assumed, not measured (mock ids are globally unique by construction).
- The tracer's in-process key does not give custody (§5). The out-of-process recorder is a design, not run.
- Provenance is value co-occurrence. Derived and computed values need a derivation-aware checker.
- Human interaction in the TUI (not RPC) was not driven. `user_bash` and `input.source:"interactive"` are [SRC]/[RUN-rpc] only.

## Reproduction

```
cd scratchpad/accountability/pi
python3 run_pi.py g2 global                          # memo scenario, child traced
python3 run_pi.py e1 e_only                          # tracer via -e only (child untraced)
python3 run_pi.py p1 global --scenario parallel_sub  # parallel sub-agents: env link vs content join, fs mis-attribution
python3 run_pi.py m1 e_only --extra mutate.ts        # args + message rewrite
python3 run_pi.py m2 global --extra mutate2.ts       # tool_result rewrite (tracer last)
python3 run_pi.py rq1 global --scenario req          # requirement / delegation-task errors
python3 run_pi.py f1 e_only --scenario fail          # validation / unknown / execution errors
python3 run_pi.py ed1 e_only --scenario edit         # edit details.patch
python3 run_pi.py bp1 global --scenario bashpi       # nested pi via bash
python3 run_pi.py k_SIGINT global --scenario slow --kill-after 2.5 --kill-sig SIGINT
python3 rpc_probe.py                                 # human bash, set_model, fork
python3 trace_pi.py runs/g2 [--session-only]
/home/user/Vacant/.venv/bin/python verify_chain.py runs/g2/trace/trace-<pid>.jsonl [--tamper 40]
```
