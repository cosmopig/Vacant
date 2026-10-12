# OpenCode 1.18.32: capturing the trajectory (who did what) for accountability

Lens: what a person running **one** OpenCode agent can hand to Vacant, so that Vacant can
(1) record who did what as it happens, (2) trace a failed check on the deliverable back to the step that caused it, and
(3) attribute that step to an actor (agent / sub-agent / model), telling "the input was wrong" apart from "the agent got it wrong".

The earlier sheet `scratchpad/understand/agent-opencode.md` covered pre-tool deny, stop, session end and config injection.
This sheet covers **trajectory capture** only. The task is a general one, not a coding task: write a one-line population brief from a notes file, a web page and a sub-agent's result.

## Evidence and conventions

- **Binary:** `opencode-ai@1.18.32` at `scratchpad/agents/node_modules/.bin/opencode`.
  - It is a Bun-compiled ELF. The model requests carry the User-Agent `opencode/1.18.32 ai-sdk/provider-utils/4.0.23 runtime/bun/1.3.14`.
  - Snapshots use the system git, version 2.43.0.
- **Source:** tag `v1.18.32`, mirrored at `scratchpad/ocsrc/v1.18.32/`. This round added `tool/task.ts`, `session/message-v2.ts`, `session/processor.ts`, `snapshot/index.ts`, `core/src/session/sql.ts`, `core/src/database/database.ts`, `schema/src/v1/session.ts`, `storage/storage.ts` and `server/.../handlers/event.ts`.
  - Paths in [SRC] tags are relative to `packages/opencode/src/` unless another package is named.
- **Model backend:** `accountability/opencode/mock_oc.py`, a scripted OpenAI Chat Completions SSE mock.
  - It is derived from `/home/user/Vacant/ops/intake/mock_model.py`.
  - It adds routes (by the first or last user text), parallel tool calls, `reasoning_content`, `{{ws}}`/`{{port}}`/`{{last_task_id}}` substitution, and a `GET /web/...` document server that stands in for "the web".
  - Every request body and its headers are dumped to `mock/req_NNN.json`, without `Authorization`.
  - The fake key is `sk-fake-offline-000`. No real model API was contacted and no credential file was read.
- **Probe plugin:** `accountability/opencode/trace.mjs`.
  - It is loaded through `OPENCODE_CONFIG_CONTENT` `plugin:["file:///…/trace.mjs"]`.
  - Every hook is logged synchronously (`appendFileSync`) to `runs/<label>/trace.jsonl`.
  - It also injects `x-vacant-session/-user-msg/-agent` request headers (`chat.headers`) and `VACANT_SESSION_ID`/`VACANT_CALL_ID` (`shell.env`).
- **Drivers**, all under `accountability/opencode/`:
  - `run_oc.py` makes one isolated run. It uses `env -i`, puts `HOME`/`XDG_*` under `runs/<label>/`, `git init`s the workspace, passes `--dir <abs>` and `PWD=ws`, and redirects stdin from `/dev/null`. After the run it dumps every SQLite table to `db_dump.json`, lists the data directory and runs `opencode --pure export <sid>` for each session.
  - `run_serve.py` is the `serve` + SSE attempt.
  - `trace_oc.py` is the post-hoc reconstruction and trace-back.
- **Raw evidence** for each run is in `runs/<label>/`: `stdout.jsonl`, `stderr.txt`, `rc.txt`, `trace.jsonl`, `db_dump.json`, `data/opencode/{opencode.db*,snapshot/,log/,tool-output/}`, `export_<sid>.json`, `mock/`, and `traceback.json` where the trace-back was run.

| label | what it exercises |
|---|---|
| S1_single | read → webfetch (local page) → bash → write (wrong figure 421,300) → edit → bash `>>` append; a single agent |
| S2_subagent | parent `task` → child (`general`, **model `mock/m2`**) reads notes (412,300) and writes `figure.txt` = 421,300 via bash → parent reads `figure.txt` → writes the brief. The **sub-agent introduces** the error |
| S2b_badinput | same as S2, but `notes.txt` already says 421,300. The **input is wrong** |
| S3_parallel / S3b_parallel_cont | 5 tool calls in one model response: 2 bash, a read of a missing file, a write outside the workspace (rejected), and an edit that fails; then `exit 3`. S3b adds `experimental.continue_loop_on_deny` |
| S4_pure | S1 with `--pure` (no plugins) |
| S5_served_model | the mock answers `model: "served-xyz-9"` in every chunk |
| S6_tamper | the agent's own bash rewrites `opencode.db` (part and event rows) and appends to the plugin log |
| S7_parallel_tasks | two `task` calls in one response. The children run concurrently and write `a.txt` and `b.txt` |
| S8_serve_sse | `opencode serve` with an SSE subscriber, plus `run --attach` (no plugin) |
| S9_resume | a second `task` call with `task_id` = the first child, which resumes the same child session |
| S10_nogit | S1 in a non-git workspace |
| S11_trunc | bash producing 60,000 lines of output (truncation) |
| S12_rewrite | a second plugin rewrites bash args in `tool.execute.before` |

Every run exited with rc=0 (`rc.txt`). The S3 run also exited with rc=0, although it ended on a permission rejection.

---

## 0. Bottom line

1. **OpenCode already keeps a per-session, sequenced, durable event log.** SQLite table `event(id, aggregate_id, seq, type, data)` with `aggregate_id` = sessionID and gap-free `seq` 0..N [RUN S1: 88 rows, seq 0..87]. It stores `session.created.1`, `session.updated.1`, `message.updated.1`, `message.part.updated.1`, including **every tool state transition** (`pending → running → completed|error`).
   - The live plugin `event` hook delivered **exactly** the same set: counts are equal per type in S1, S2 and S7.
   - The live event `id` equals the row `id` (`evt_…`) [RUN S2: 92/92 joined]. So a live record can be pinned to `(aggregate_id, seq)`.
2. **One assistant message = one model call ("turn").**
   - Each turn has a `step-start` part holding the worktree **tree hash before** the call, and a `step-finish` part holding the **tree hash after** its tools finished. When files changed there is also a `patch{hash: <before tree>, files[]}` part.
   - The trees live in a private git repo at `$XDG_DATA_HOME/opencode/snapshot/<projectID>/<hash(worktree)>/`. **Bash-made changes are captured too** [RUN S1: the `>>` append shows up as a patch on the bash turn]. That makes content-addressed, per-turn "who changed which file" possible after the fact.
   - Snapshots need `project.vcs === "git"` [SRC `snapshot/index.ts:167-170`]. A non-git workspace gets **no** snapshots or patches [RUN S10].
3. **Every join key needed for attribution is present:**
   - `callID` (the model's tool-call id, e.g. `call_2_1`, byte-identical to the id the provider emitted) → tool `part.id` → `messageID` (turn: `modelID`, `providerID`, `agent`, `mode`, `parentID` = the user or hand-off message) → `sessionID` (actor) → `session.parent_id`.
   - The sub-agent hand-off is the parent's `task` tool part: `state.input.prompt` plus `state.metadata.sessionId` = the child session, which is set while the call is **running**, before the child's first message [RUN S2 seq 79 < 82].
4. **Trace-back works end to end on the durable record alone** (`trace_oc.py`, [RUN]):
   - S1 → `AGENT_INTRODUCED` by `build`/`mock/m` at `call_5_1` (write).
   - S2 → `brief.md` copied from `read figure.txt` → `figure.txt` written by the **child** `general`/`mock/m2` bash `call_4_0` → `AGENT_INTRODUCED`.
   - S2b → the same two hops, then `notes.txt` already held 421,300 in the pre-run tree → `INPUT_WRONG`.
   - S6 → the DB had been rewritten → `MISMATCH(db!=live)` against the plugin record.
5. **Not tamper-evident, and not always faithful:**
   - (a) The agent's own bash rewrote the `part` and `event` rows and appended to the plugin log [RUN S6]. Nothing is signed or chained.
   - (b) **Args rewritten by a plugin are stored as if the model had emitted them.** The DB, the event rows and even the history replayed to the model show the rewritten args. The model's original args exist only in a plugin that ran earlier, or at a model proxy [RUN S12].
   - (c) The **served** model id is never recorded, only the configured one [RUN S5].
   - (d) The system prompt is not persisted [RUN].
   - (e) Snapshot patches are **time-window, worktree-wide** diffs. With concurrent sub-agents, one child's patch lists the sibling's file [RUN S7]. `--pure` removes the plugin but not the DB, snapshots or log [RUN S4].
6. **`opencode run --format json` stdout is not a trajectory.** It contains only the root session's `step_start`/`tool_use`/`step_finish`/`text` (completed or error only); no sub-agent tool calls, no model ids, no user or hand-off messages [RUN S2].
7. **There is no `storage/` JSON tree in 1.18.32.**
   - Sessions, messages and parts are SQLite rows in `$XDG_DATA_HOME/opencode/opencode.db` (WAL mode). No `storage/` directory was created in any run [RUN].
   - `storage/storage.ts` survives only as a legacy JSON KV with migrations [SRC `storage.ts:224`].
   - The "session/message/part files" layout in the task brief is from older versions.

---

## 1. Channel × fact matrix

Columns:
- **Live plugin**: in-process hooks.
- **DB**: `opencode.db` after the run.
- **Snapshot**: the per-turn git trees.
- **stdout**: `run --format json`.
- **Model proxy**: request and response on the wire (the mock logs stand in for it).

| fact | live plugin | DB | snapshot | stdout | model proxy |
|---|---|---|---|---|---|
| tool call: tool, callID, sessionID, args | `tool.execute.before` (args **before** later plugins) + part events | `part` (args **after** plugins) | – | root only, final state | response `tool_calls` (original args) |
| tool result | `tool.execute.after` (**not for errors**); part `completed`/`error` | `part.state.output/error/metadata` | – | root only | next request's `role:"tool"` message |
| which turn issued it | part event `messageID` (arrives before `tool.execute.before`) | `part.message_id` | – | `part.messageID` | call id in that response |
| turn → model / agent | `message.updated` (`modelID`, `providerID`, `agent`, `mode`) | `message.data` | – | – | request `model` + **served** `model` |
| actor = session, parent | `session.created` `info.parentID`, `agent`, `model` | `session.parent_id/agent/model` | – | root `sessionID` | header `x-session-id` (native) |
| hand-off prompt → child | task part `input.prompt` + `metadata.sessionId`; child user text part | same | – | root task `tool_use` only | child's first request |
| files changed per turn (any tool incl. bash) | `patch` part event | `patch` part, `step-*` snapshots | trees/blobs | `step_*.snapshot` | – |
| files changed per **call** | write/edit: `metadata.filepath`/`diff`; bash: none | same | – | same | – |
| what the model saw in this turn | `experimental.chat.messages.transform` (full list) + `system.transform` | reconstructable except the system prompt, compaction and truncation | – | – | request body (exact) |
| permission asked / answered | `permission.asked` (`tool.callID`) / `permission.replied` | **not stored** (log only) | – | stderr text | – |
| reasoning text | `reasoning` part | `reasoning` part | – | only `--thinking` | response |
| token usage | step-finish `tokens` | same | – | `step_finish.part.tokens` | response `usage` |

---

## 2. (a) Tool hooks: inputs and outputs [RUN S1/S2/S3b]

- `tool.execute.before(input, output)`:
  - input is `{"tool":"write","sessionID":"ses_…","callID":"call_5_1"}`.
  - output is `{"args":{…}}`, which is mutable.
  - Awaited, sequential across plugins [SRC `session/tools.ts:106-110`, `plugin/index.ts:284-297`].
  - Fires for built-in tools, MCP tools, `task`, and the subtask path (`session/prompt.ts:307`, where `callID` = part id).
- `tool.execute.after(input, output)`:
  - input is `{tool, sessionID, callID, args}`.
  - output is `{title, output, metadata}`.
  - **Only on success**: the call sits after `item.execute` in the same Effect [SRC `tools.ts:112-125`].
  - It did **not** fire for the read of a missing file, the failed edit or the rejected write [RUN S3b seq 89/90/92]. Errors are visible only as part events `state.status:"error"` with `state.error`.
- Non-zero bash exit is **not** an error: `status:"completed"`, `metadata.exit: 3` [RUN S3b].
- `metadata` by tool [RUN S1]:
  - `read`: `{preview, truncated, loaded[], display{type:"file", path, text, lineStart, lineEnd, totalLines}}`. The output contains the content read, with line numbers.
  - `webfetch`: `{truncated}` only. The URL is in args and the fetched body is in `output`.
  - `bash`: `{output, exit, truncated[, outputPath]}`. No file list.
  - `write`: `{diagnostics, filepath, exists, truncated}`.
  - `edit`: `{diagnostics, diff (unified), filediff{file,…}}`.
  - `task`: `{parentSessionId, sessionId, model{modelID, providerID}, truncated}`.
- **Truncation** [RUN S11]: 60k lines of bash output → `state.output` 12,220 chars beginning `...output truncated...\n\nFull output saved to: $XDG_DATA_HOME/opencode/tool-output/tool_<id>`, with `metadata.outputPath` set. The full text lives in that file, not in the DB.
- **Arg rewrite provenance** [RUN S12]:
  - The model emitted `{"command":"REWRITE_ME"}`, and a plugin changed it to `echo rewritten-by-plugin > r.txt`.
  - `trace.mjs` was first in `plugin[]`, so its `tool.execute.before` logged `REWRITE_ME`.
  - The durable events show `pending` with `input:{}`, then `running` and `completed` with the **rewritten** command. The next request replayed the **rewritten** `tool_calls` to the model.
  - OpenCode keeps no record of the original args.
  - [INF] A Vacant plugin loaded from `OPENCODE_CONFIG_CONTENT` (config layer 6) runs **after** global and project plugins (earlier merge layers), so it may see already-rewritten args. Only a model-side proxy sees the true emission.
- `shell.env({cwd, sessionID, callID}, {env})` fires once per bash call. The injected `VACANT_CALL_ID` is visible inside the process (`CALL=call_4_0`) [RUN S1], including in the child (`SUBCALL=call_4_0 SUBSES=ses_…`) [RUN S2]. That tags anything the bash process writes or sends with the call id.
- Ordering within one call [RUN S2]:
  - part `pending` (has `messageID`)
  - `tool.execute.before`
  - part `running`
  - bash partial-output `running` updates
  - `tool.execute.after`
  - part `completed`
- Parallel calls in one response [RUN S3]: all five `before` calls fire in model order; completion order differs (b before a).

## 3. (b) Event stream relevant to a trajectory [RUN]

Plugin `event({event})` receives `{id, type, properties}`.
- It is **fire-and-forget** (`void hook.event(...)`, `plugin/index.ts:255-262`), but its synchronous prefix runs in bus order.
- It is filtered to the instance directory.
- `message.part.delta` fires per streamed chunk (`{sessionID, messageID, partID, field, delta}`).

Types seen in S1 (with counts):
- durable: `session.created`×1, `session.updated`×11, `message.updated`×29, `message.part.updated`×47
- live-only: `session.status`×16, `session.idle`×1, `session.diff`×8 (all empty `diff:[]`), `file.edited`×2, `file.watcher.updated`×2, `message.part.delta`×3, `plugin.added`, `catalog.updated`, `integration.updated`, `reference.updated`
- S3 adds `permission.asked` / `permission.replied`.

Exact shapes, excerpted from `runs/S2_subagent/trace.jsonl` (`$R` = the run dir):

```json
{"id":"evt_0d4740e94002zcfnpuZlVE9Yrf","type":"session.created","properties":{"sessionID":"ses_f2b8bf16bffejlrxDb1F2Gcmxv",
 "info":{"id":"ses_f2b8bf16bffejlrxDb1F2Gcmxv","slug":"witty-star","version":"1.18.32","projectID":"456a4b2b…","directory":"$R/ws","path":"",
 "parentID":"ses_f2b8bfb6cffehVJ2m3Z60BJAFJ","title":"Extract population figure (@general subagent)","agent":"general",
 "permission":[…,{"permission":"task","pattern":"*","action":"deny"}],"time":{"created":1790270770836,"updated":1790270770836}}}}

{"id":"evt_0d474104f0014iDgk0BtIfQPwI","type":"message.updated","properties":{"sessionID":"ses_f2b8bf16…",
 "info":{"id":"msg_0d4740ebf001G01YEnBqCJ6cqs","parentID":"msg_0d4740ea2001x5N2KpF4kn09kM","role":"assistant","mode":"general","agent":"general",
 "path":{"cwd":"$R/ws","root":"$R/ws"},"tokens":{"total":110,"input":103,"output":7,"reasoning":0,"cache":{"write":0,"read":0}},
 "modelID":"m2","providerID":"mock","time":{"created":1790270770879,"completed":1790270771278},"finish":"tool-calls"}}}

{"id":"evt_0d4740e9c001Eihru79vMHQxdQ","type":"message.part.updated","properties":{"sessionID":"ses_f2b8bfb6…","time":1790270770844,
 "part":{"id":"prt_0d4740e85001QbeTwuJKfGf701","messageID":"msg_0d47409c8001wXn7cgG0q44v1G","type":"tool","tool":"task","callID":"call_2_1",
  "state":{"status":"running","title":"Extract population figure","input":{"description":"Extract population figure",
   "prompt":"SUBTASK-A: read notes.txt and write the population figure (digits only) to figure.txt","subagent_type":"general"},
   "metadata":{"parentSessionId":"ses_f2b8bfb6…","sessionId":"ses_f2b8bf16…","model":{"providerID":"mock","modelID":"m2"}},"time":{"start":1790270770844}}}}}

{"type":"message.part.updated","properties":{"part":{"type":"patch","hash":"4c73315c…","files":["$R/ws/figure.txt"],
 "messageID":"msg_0d4741055001c6uvvXdX2YpSGz","sessionID":"ses_f2b8bf16…"}}}

{"type":"permission.asked","properties":{"id":"per_0d464ab54001Jc4oRLMh6bhdKH","sessionID":"ses_f2b9b610…","permission":"external_directory",
 "patterns":["/tmp/*"],"metadata":{"filepath":"/tmp/vacant_oc_external_probe.txt","parentDir":"/tmp"},"always":["/tmp/*"],
 "tool":{"messageID":"msg_0d464a5bd0017IiGR1heby8pYM","callID":"call_2_3"}}}
```

- The user message info is `{id, role:"user", sessionID, time.created, agent, model{providerID, modelID}}`. Later it gains `summary.diffs[]`, a unified patch per file for the whole turn [RUN S1].
- **Model or agent id per turn:**
  - The assistant `message.updated` carries `modelID`/`providerID`/`agent`/`mode`/`variant`.
  - For the sub-agent it was `m2`, from `agent.general.model` [RUN S2].
  - The session row also stores `model{id, providerID, variant}` and `agent`.
- **Hooks around each model call**, in order, per turn [RUN S2]:
  - new assistant `message.updated`
  - `experimental.chat.messages.transform` (its input is `{}`; the session is inferred from the messages)
  - `experimental.chat.system.transform`
  - `chat.params`
  - `chat.headers`
  - `step-start`
- `chat.params` and `chat.headers` get `{sessionID, agent, model, provider, message}`, where **`message` is the user message, not the assistant turn**. To tag the request with the turn, remember the latest new assistant message per session.
- The title-generation call has `agent:"title"` and no assistant message.
- OpenCode itself sends `x-session-id` and `x-session-affinity` = sessionID on every model request, **even under `--pure`** [RUN S4 mock log]. A proxy can therefore attribute requests to actors without a plugin.
- **Model identity:** OpenCode records the **configured** `modelID`. The response `model` (`served-xyz-9`) appears nowhere: not in the DB, trace, stdout or `opencode.log` [RUN S5]. The log only has `message=stream providerID=mock modelID=m session.id=… small=false agent=build`.
- **Permissions** [RUN S3]:
  - A rejected permission ends the loop by default (`experimental.continue_loop_on_deny`, `processor.ts:647`). The final assistant message then has `finish:"tool-calls"` and no `stop` turn, with rc=0.
  - `permission.*` events are **not** in the durable `event` table and the `permission` table stayed empty. Decisions survive only in `opencode.log` (`message=evaluated permission=bash pattern="…" action.action=allow`) and in the error text of the tool part.

## 4. (c) On-disk session storage and post-hoc reconstruction [RUN]

`$XDG_DATA_HOME/opencode/` after S1:
- `opencode.db` (4 KB), `opencode.db-wal` (3.1 MB, not yet checkpointed; `mode=ro` readers see it), `opencode.db-shm`
- `snapshot/<projectID>/<hash>/` (a git dir whose `objects/info/alternates` points at `ws/.git/objects`)
- `log/opencode.log`
- `repos/`
- `tool-output/` (only when truncation happens)

There is no `storage/`.
- The DB path is `Global.Path.data/opencode.db`, or `opencode-<channel>.db`, or `OPENCODE_DB` [SRC `core/src/database/database.ts`].
- 20 tables. The ones that matter here:
  - `session(id, project_id, parent_id, slug, directory, title, version, agent, model json, permission json, summary_* , tokens_*, cost, time_*)`
  - `message(id, session_id, time_created, time_updated, data json)`: `data` = the v1 `User`/`Assistant` info minus id/sessionID.
  - `part(id, message_id, session_id, time_*, data json)`: the final state of each part.
  - `event(id, aggregate_id, seq, type, data json)` + `event_sequence(aggregate_id, seq, owner_id)`: **the durable, ordered history, including intermediate tool states**. There is no timestamp column; times sit inside `data`.
  - `project(id, worktree, vcs, …)`: non-git gives `id:"global", worktree:"/", vcs:null` [RUN S10].
  - The `permission`, `session_message`, `session_input` and `todo` tables were empty in these runs.
- **IDs sort by creation time** (`msg_`/`prt_`/`evt_` + an ascending id). `ORDER BY id` gives creation order [SRC `schema/src/v1/session.ts` `ascending()`; RUN].
- **Snapshots:**
  - Tree hashes are real git trees. `git --git-dir <snap> ls-tree <hash>` lists the files, and `git diff <before> <after>` shows the turn's change [RUN S1: `4c73… → 9725…` adds `brief.md`; `38fa… → 80ac…` shows `+Sources: …`, which bash appended].
  - Blob ids = `git hash-object <file>`, so the **delivered file can be matched byte-for-byte to the turn that produced it**. In S2, deliverable blob `64ead13d…` = `blob_after` of hop 0.
  - Limits [SRC `snapshot/index.ts:24,167-300`]:
    - git only, unless `snapshot:false`
    - the git worktree only (the whole repo if the workspace is a subdirectory)
    - `.gitignore`d files are excluded
    - untracked files > 2 MB are excluded
    - taken at `step-start` (before streaming) and `step-finish` (after that turn's tools) [SRC `processor.ts:424-485`]
- **`opencode export <sid>`** returns `{info, messages:[{info, parts}]}`, one session per call. The child needs its own export. It holds final states only, with no event seq.
  - It took **54 s** without `--pure` and **1.5 s** with `--pure` [RUN S4]. It re-loads plugins and the dependency install; see §9.
- **Reconstruction recipe (post-hoc only):**
  - sessions → tree by `parent_id`
  - messages per session in id order: user = prompt or hand-off; each assistant = one turn with model/agent
  - parts per message: `step-start.snapshot`, tool parts (callID, input, output, metadata, time), `step-finish.snapshot` + tokens, `patch.files`
  - `event` rows per aggregate by seq, for intermediate states and ordering
  - snapshot trees for file contents per turn
  - `tool-output/` for full outputs
  - Implemented in `trace_oc.py` (`Run.__init__`).

## 5. (d) Sub-agents: the `task` tool and how children link [RUN S2/S7/S9 + SRC `tool/task.ts`]

- **Parameters:** `{description, prompt, subagent_type, task_id?, command?, background?}`. `background` needs `OPENCODE_EXPERIMENTAL_BACKGROUND_SUBAGENTS=true`.
- **Child creation:**
  - `sessions.create({parentID: ctx.sessionID, title: description + " (@<agent> subagent)", agent, permission})`.
  - Default `subagent_depth` is 1, and the child gets `task: deny` [RUN: the child permission lists it], so grandchildren are refused.
  - The child's model is `agent.model ?? parent turn's model` [SRC `task.ts`; RUN S2: `m2`].
- **Link fields:**
  - Parent tool part: `state.metadata = {parentSessionId, sessionId, model}`. It is present from `running` onwards (`ctx.metadata`), and the output is `<task id="ses_…" state="completed"><task_result>…last text…</task_result></task>`.
  - Child side: `session.parent_id`, `session.title`, and its **first user message text = `input.prompt`** (the hand-off).
  - The child session does **not** store the parent callID. The call→child link lives on the parent part. A callID→child map can be built from `metadata.sessionId`, cross-checked by `parent_id` [RUN].
- **Result flow:** the parent sees only the child's **last text part** (`Wrote 421,300 to figure.txt`) via the tool output. The child's tool calls and outputs are only in the child session.
- **Resume** (`task_id`) [RUN S9]: two parent calls (`call_2_0`, `call_5_0`) mapped to the **same** child session, which kept the first title "First pass (@general subagent)". The child's user messages carry each prompt. Matching a child user message to a parent call needs prompt equality plus time containment (parent `time.start` < child `message.time.created` < parent `time.end`).
- **Concurrent children** [RUN S7]: two tasks in one response ran in parallel.
  - The slow child's patch listed `a.txt` **and** `b.txt`. `b.txt` was written by the fast sibling during the slow child's window.
  - The parent's task turn listed both too.
  - Patch parts are therefore **not actor-scoped**. `trace_oc.py` resolves this by preferring the turn that has a call naming the file (`candidate_steps` = [fast child, slow child, parent]). With bash commands that do not name their outputs, it stays ambiguous.
- **Child-first ordering:** the child's `session.idle` fires before the parent `tool.execute.after(task)` [RUN S2 seq 151 < 152]. The child's patch also re-appears in the parent's task turn, so the innermost session must win.

## 6. Trace-back demo: `trace_oc.py` [RUN]

The input is the run directory. It reads only `opencode.db` and the snapshot repo, plus the plugin log for the cross-check. The check stands in for a contract rule: `brief.md` must not contain `421,300`; the census figure is 412,300.

Algorithm:
1. Find the earliest turn whose after-tree has the token in the file and whose before-tree does not. Prefer turns with a call that names the file, then the deepest session, then the earliest finish.
2. The writer is that turn's call touching the file: `filePath` for write/edit, the command text for bash.
3. Collect the actor's completed observations before the writer started, and find one whose output contains the token:
   - `read` → recurse into that file before that time;
   - `task` → recurse into the child;
   - webfetch/bash output → `INPUT_WRONG` (external);
   - the actor's prompt contains the token → `INPUT_WRONG`;
   - none → `AGENT_INTRODUCED`.
4. A file already containing the token in the first turn's before-tree → `INPUT_WRONG`.

Every hop carries these fields:
- `actor{session, parent_session, agent, mode, model, model_turn}`
- `tree_before`, `tree_after`, `blob_after`, `patch_files`
- `writer{callID, tool, part, time, input_sha256, output_sha256, durable_event{aggregate, seq, row_sha256}, live_plugin}`
- `source{…}`, `candidate_steps`, `verdict`

Results (`runs/*/traceback.json`):

| run | chain | attribution |
|---|---|---|
| S1 | brief.md ← `write call_5_1` (turn `msg_0d46207f5001zszCzSB6WR7uKn`); 3 earlier observations (notes 412,300, web 412,300, `wc`) lack the token | **AGENT_INTRODUCED**: `build`, `mock/m`, `call_5_1` |
| S2 | brief.md ← `write call_7_0` (parent `build`/`m`) ← source `read figure.txt call_6_0` → figure.txt ← child turn `msg_0d4741055001c6uvvXdX2YpSGz` bash `call_4_0` (`general`/`mock/m2`, parent `ses_f2b8bfb6…`); its only observation (`read notes.txt call_3_1`) said 412,300 | **AGENT_INTRODUCED** by the sub-agent; the parent is a propagator (`COPIED_FROM_FILE`) |
| S2b | brief.md ← `call_7_0` ← `read figure.txt` → figure.txt ← child `call_4_0` ← `read notes.txt call_3_1` → notes.txt already 421,300 in initial tree `ba371eb6…` (blob `5a56a4ce…`) | **INPUT_WRONG**: both agents only copied |
| S6 | brief.md ← `write call_2_0`; the DB says its input was "412,300", the live record says "421,300" | writer `live_plugin: "MISMATCH(db!=live)"`, DB tampering detected |

Evidence the chain carries that a third party can re-check:
- the git blob and tree ids, recomputable from content;
- `(aggregate_id, seq)` of the durable event row for each cited call;
- sha256 of the row and of the input and output.

What is **not** re-checkable without Vacant's own signing: that those rows were not edited after the fact (S6).

The token-matching step (3) is a demo heuristic [INF]. Real general tasks need a claim-level matcher. The point measured here is that every input an actor saw before its writing call is on record, with ids and times.

## 7. (e) What is NOT observable, or only partly

| gap | evidence | what closes it |
|---|---|---|
| Original model args when any plugin rewrites them; history replayed to the model is rewritten too | RUN S12 | Vacant plugin first in order (not guaranteed via CONTENT, [INF]) or a model-side proxy |
| Served model / actual upstream identity | RUN S5 | proxy (response `model`, headers) |
| Assembled system prompt (instructions, AGENTS.md, env block; 9,755 chars in S1) | RUN: absent from DB | `experimental.chat.system.transform` hook (hash or store) or proxy |
| What a later turn actually saw after compaction/prune (`[Old tool result content cleared]`) or `toolOutputMaxChars` truncation | SRC `message-v2.ts:297-300` | `experimental.chat.messages.transform` hash per turn, or proxy |
| Files a bash call read; network a bash call made | RUN: only command + output | `VACANT_CALL_ID` via `shell.env` + an OS-level tracer or sandbox (outside OpenCode) |
| Files a bash call wrote, **per call** | RUN S3 (one patch for 2 parallel bash), S7 (sibling leakage) | per-call pre/post snapshot in `tool.execute.before/after` (still ambiguous under concurrency) or per-process write attribution |
| Changes outside the git worktree, gitignored, or > 2 MB untracked; any change in a non-git workspace | SRC snapshot; RUN S10 | `git init` the workspace; Vacant hashes the declared deliverables itself |
| Permission decisions (durably) | RUN S3: not in `event`/`permission` tables | capture `permission.asked/replied` live (they carry `tool.callID`) |
| Failed tool calls in `tool.execute.after` | RUN S3b | use part events (`status:"error"`) |
| Sub-agent activity in `run --format json` stdout | RUN S2 | plugin events or DB |
| Integrity of the DB, snapshot repo and plugin log (agent's bash can write all three; `external_directory` did not trigger because the path came from `$XDG_DATA_HOME`) | RUN S6 | stream each event out of process as it happens, into a hash-chained, signed Vacant logbook the agent cannot write to |
| Everything plugin-based under `--pure` / `OPENCODE_PURE=1` | RUN S4 (DB + snapshots still written) | reject `--pure`, strip `OPENCODE_PURE`; fall back to the post-hoc DB |
| Out-of-process live stream via `opencode serve` SSE | RUN S8: `/event?directory=` and `/global/event` returned **no bytes** within 6–120 s in this container (with and without `OPENCODE_SERVER_PASSWORD`, curl `--noproxy`); `run --attach` itself worked (6.3 s) | not verified here; root cause unknown. [SRC `handlers/event.ts`] says it should emit `server.connected` and then instance events |
| Human edits in the TUI, `/undo` revert (`message.removed`/`part.removed`, `session.revert`) | not run (headless only) | [SRC] events exist; capture them live |

## 8. Capture recipe for Vacant (OpenCode adapter)

1. **Launch** [RUN]:
   - `git init` the workspace (without it there are no snapshots or patches).
   - Command: `opencode run --format json --dir <abs ws> -m <provider/model> "<prompt>"` with `PWD=<ws>`, `cwd=<ws>` and `stdin=/dev/null`.
   - Pass `OPENCODE_CONFIG_CONTENT` deep-merged with `plugin:["file:///abs/vacant-trace.mjs"]`.
   - Refuse `--pure` and strip `OPENCODE_PURE`. Keep `snapshot` at its default (true).
   - Pre-seed `$XDG_CONFIG_HOME/opencode/node_modules/@opencode-ai/plugin` (see §9).
2. **Live capture in the plugin.** Do all work synchronously, because `event` is not awaited and `run` exits about 40 ms after idle. Forward each record at once over a local socket to a separate Vacant recorder process that hash-chains and signs it; the agent's uid must not hold the signing key.
   - `event`:
     - `session.created` → actor `{sessionID, parentID, agent, model}`
     - `message.updated` → turn `{messageID, sessionID, modelID, providerID, agent, mode, parentID}`
     - `message.part.updated` → tool `{callID, messageID, status, input, output|error, metadata, time}`, plus `step-start`/`step-finish` snapshots, `patch.files` and `reasoning`/`text`
     - `permission.asked`/`permission.replied` → `{id, permission, patterns, tool.callID, reply}`
     - `session.idle` (filter out children)
     - Keep `event.id` so the durable `(aggregate_id, seq)` can be joined later.
   - `tool.execute.before` → original args (as far as plugin order allows) keyed by `callID`.
   - `experimental.chat.messages.transform` and `experimental.chat.system.transform` → sha256 of the exact context of each turn.
   - `chat.headers` → add `x-vacant-turn: <latest assistant msg id of this session>` for the optional proxy. OpenCode already sends `x-session-id`.
   - `shell.env` → `VACANT_CALL_ID`, `VACANT_SESSION_ID` into every bash process.
3. **Post-run seal:**
   - Read `opencode.db` (`session`, `message`, `part`, `event`) with the same `XDG_DATA_HOME`.
   - Read the snapshot trees and `tool-output/`.
   - Run `opencode --pure export <sid>` for each session.
   - Cross-check every DB row against the signed live record by `evt_` id; a mismatch = tampering (S6).
   - `git hash-object` each deliverable and bind it to the tree of the last turn.
4. **Trace-back** (`trace_oc.py`):
   - failing claim → first turn containing it (snapshot) → writer call → the actor's prior observations → recurse through files and hand-offs;
   - verdict `AGENT_INTRODUCED` (actor = session, agent, model, callID) versus `INPUT_WRONG` (pre-existing file, web output, prompt);
   - propagators are listed separately.

   These map onto the repo's reputation keys: stream = the agent identity, branch = the (sub-)agent role (`agent` name / session), substrate = `providerID/modelID`.

## 9. Side effects observed while measuring (they matter for an offline exhibition)

- With any plugin configured, OpenCode ran `npm install @opencode-ai/plugin@1.18.32` into `$XDG_CONFIG_HOME/opencode/` and **waited** for it before loading plugins.
  - [RUN] `cfg/opencode/{package.json, package-lock.json, node_modules/}` appeared, with `resolved` URLs on `registry.npmjs.org`.
  - This container allowed direct egress (curl 200 without proxy variables), so the install reached the registry. It was not a model API and no key was used.
  - It cost about 10.5 s per run (log gap 13.9 → 24.4 s). Runs with the plugin took 14–19 s (`rc.txt`); `--pure` took 6.8 s.
  - [SRC `config/config.ts:452-470`, `plugin/index.ts:184`]
  - Pre-seed that directory, or expect a delay or failure offline.
- `opencode export` without `--pure` re-triggers plugin loading, which took 54 s here.

## 10. Gaps / not verified

- SSE (`serve` `/event`, `/global/event`) produced nothing in this container, so the out-of-process live channel is unverified (§7).
- Plugin ordering between global, project and CONTENT plugins was not measured, only inferred [INF].
- Compaction and prune were not triggered; their effect on "what the model saw" comes from source only.
- TUI-only flows (`/undo`, revert, manual edits, `@agent` subtask parts via `prompt.ts:300`) were not run.
- Background sub-agents were not run.
- MCP tools were not re-run this round. The earlier sheet has them passing through `tool.execute.before` as `<server>_<tool>`.
- OpenTelemetry (`experimental.openTelemetry`, [SRC `session/llm.ts`]) was not tested.
- The trace-back uses substring matching of a token. It shows the data suffices for the mock scenarios, not that it generalises to free-text claims.
- The mock returns scripted tool calls, so "agent error" here means "the scripted actor wrote a value none of its inputs had". This is L-fake evidence about the capture plumbing, not about model behaviour.
