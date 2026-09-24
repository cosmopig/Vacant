# Completeness critique of the six accountability sheets

Date: 2026-09-24. Critic lens over `capture-claude.md`, `capture-codex.md`, `capture-opencode.md`,
`capture-pi.md`, `repo-accountability.md` and `literature.md`, all in `scratchpad/accountability/`.

The goal being served: an **accountability layer for general (not only coding) tasks** while a person drives one
agent. It must (1) record who did what, live and signed; (2) when a check on the deliverable fails, trace back to the
step, its inputs and its actor; (3) attribute responsibility, separate "input/requirement wrong" from "agent wrong",
and feed consequences into reputation and routing. The user's objection to the current version is that it is "several
local verifiers", not accountability that finds the error point. So this critique asks one question of every sheet:
**does the design of (1)–(3) have the facts it needs?**

Rules kept: nothing under `/home/user/Vacant` was modified; every model call went to a local scripted mock; Claude
Code ran with `ANTHROPIC_API_KEY=sk-fake-offline-000`, `ANTHROPIC_BASE_URL=http://127.0.0.1:<mock>` and an isolated
`HOME`; Codex used `MOCK_KEY=sk-fake-not-real` and an isolated `CODEX_HOME`. No credential file was read.

Tags: **[RUN]** I executed it and saw it (critic lab below); **[RUN-sheet]** a sheet's [RUN] that I re-checked in its
raw data; **[SRC]** read in source or binary strings; **[DOC]** vendor docs saved in `scratchpad/cc/`; **[INF]**
inference.

Critic lab: `scratchpad/accountability/critic/`
- `claude/run_probe.py` (+ `hk2.py`, `attr_strace.py`, `attr_by_argv.py`), runs in `claude/out/<label>/`.
  Scenario: main Bash env dump → **two foreground `Agent` calls in one message** (each: env dump, `sleep 2`, write a
  file) → a `run_in_background` Bash → text. Flags: `rewrite` / `rewrite2` (PreToolUse `updatedInput` tag with /
  without `permissionDecision:"allow"`), `strace`, `nobg`, `shortbg`, `claudemd`, `narrow`/`narrow2`, `echoonly`.
- `codex/run_probe.py` (+ `hk_cx.py`, `scen_env.json`), runs in `codex/runs/<label>/`: root and v1 sub-agent each
  dump `/proc/self/status` and `CODEX*`/`VACANT*` env; hooks log their own `/proc/self/status`.
- `repo/probe_actorbook.py`: the committed `vacant_network/trace/actors.py`, run against a scratch book.

---

## 0. The ten things the design must absorb

1. **The repo sheet is stale.** The `trace/` package is now committed (`59e7cca9`, `764f5c1a`, `3a74cb43`), and
   `actors.py` exists. The sheet says it does not. The committed code ships the **shared `stream="main"` decay clock**
   that the sheet itself flagged as a bug. [RUN] Claude's cell mean moved from 0.55 to 0.52 purely because of 400 Codex
   events (§1.1).
2. **The four prototypes disagree on what "agent error" means** (§1.2). Claude requires that the *correct* value was
   visible to the actor. OpenCode, pi and Codex require that the *wrong* value was absent from the actor's inputs.
   A hallucinated number with no source is `AGENT_INTRODUCED` in three tracers and `undetermined/INPUT?` in
   `trace_claude.py` [SRC].
3. **Claude `-p` skips `SessionEnd` when a background Bash is still running at exit** [RUN 2/2]. The committed trace
   code seals the transcript, reads the per-step models, runs the final unrecorded-change scan and records the outcome
   **only in the `session_end` hook** [SRC `trace/capture.py:146-151`]. All of that is lost for such sessions.
   Finalization has to run in the launcher, after the process exits (§3.3).
4. **Per-call shell attribution under concurrency is solved on Linux, but not the way any sheet proposed** [RUN].
   `strace -f` plus matching the hook's `tool_input.command` inside the `bash -c` argv attributed **7/7**
   shell-written files to the exact `tool_use_id`. That includes two concurrently running sub-agents and a background
   Bash. The agent input is not modified (§3.1).
5. **Tagging commands through `updatedInput` works but is unsafe as a default** [RUN]. The tag reaches the process on
   Claude and on Codex, and the transcript and model replay keep the original command. But on Claude the prefixed
   command **no longer matches the user's narrow allow rule** (`Bash(echo:*)` → denied). Returning `"allow"` instead
   **bypasses the user's rules**. On Codex, `updatedInput` without `"allow"` is silently ignored (§3.1).
6. **Two foreground sub-agents in one Claude message run concurrently** [RUN]. Their Bash windows overlapped:
   748–2820 ms and 776–2840 ms. The Claude sheet's "mutating calls run serially, so Pre/Post diffs are attributable" is
   true only within one actor (§1.3).
7. **The shell cannot tell a Claude sub-agent from the main agent; Codex's shell can** [RUN]. In Claude, the env of a
   sub-agent's Bash is byte-identical to the main agent's: no agent id, no call id. In Codex, `CODEX_THREAD_ID` is the
   actor's own thread in every shell. OpenCode can inject `VACANT_CALL_ID` (`shell.env`) [RUN-sheet].
8. **Instruction files are model inputs that no tracer treats as inputs** [RUN]. `CLAUDE.md` reached **8/8** model
   requests, sub-agents included. It fires `InstructionsLoaded{file_path, memory_type, load_reason}` and leaves an
   `attachment.type:"instructions"` record in every transcript. A wrong value that came from `CLAUDE.md` or `AGENTS.md`
   would be blamed on the agent (§3.4).
9. **Sub-agent definition lookup in the committed `actors.definition_of` misses most real definitions** [SRC/DOC]:
   - Codex roles are `.toml`, not `.md`.
   - OpenCode's global directory is `~/.config/opencode/{agent,agents}/**`.
   - Claude and pi identify an agent by its frontmatter `name`, not by its file name. Claude also has 5 scopes.

   Custom agents therefore fall back to `builtin:<name>`. An observed alternative exists: hash the delivered system
   prompt (§3.2).
10. **Hooks run outside the Codex sandbox** [RUN]. The hook process shows `Seccomp: 0` and `NoNewPrivs: 0`; the shell
    tool shows `Seccomp: 2` and `NoNewPrivs: 1`. The Codex sheet only inferred this from an environment variable.

---

## 1. Contradictions between sheets

### 1.1 Four incompatible reputation keys, and the committed one has the collision bug

| Source | `stream_id` | `branch_id` | `substrate` |
|---|---|---|---|
| capture-codex §9 | root **session_id** (or Vacant run id) | thread id | requested model slug |
| capture-opencode §8.4 | "the agent identity" | (sub-)agent role / session | `providerID/modelID` |
| capture-pi §8.6 | agent identity (main / sub-agent `agent`+`agentSource`) | delegation path (`parent_toolCallId` chain) | `provider/responseModel` |
| repo-accountability §3 | `sha256({platform, role, definition_sha256})` | `platform/major.minor` | `observed:`/`claimed:`/`unknown` |
| **committed `trace/actors.py:57-91`** | `"main"` / `def:<name>:<sha16>` / `builtin:<type>` | `platform/<major>` (`claude/2`, **`codex/0`**) | `claimed:<model>` or `unknown` |

Why each proposal breaks something:
- **Codex's per-session stream and pi's per-run branch** create a new cell every session, so no reputation ever
  accumulates and `MIN_N=5` is never reached [INF].
- **The committed `"main"`** puts every platform's main agent on one decay clock (`Reputation._stream_seq` is keyed
  by stream only).
  - [RUN `critic/repo/probe_actorbook.py`] `key_of` returns `('main','claude/2','claimed:claude-opus-5-5','')` and
    `('main','codex/0','claimed:gpt-5.5','')`.
  - The Claude cell's mean after 2 accepted outcomes is **0.55**. After 400 Codex outcomes it is **0.52**, with no
    Claude event in between.
  - `pick_agent` uses raw counts, so routing is not affected. The displayed `mean` is.
- **`codex/0`** lumps every 0.x Codex release into one branch. The repo sheet proposed `major.minor`.

**Needed:** one rule, written once, with a globally unique stream per definition. The repo sheet's proposal is the
only one consistent with `reputation.py`'s semantics.

### 1.2 Three different definitions of "the agent got it wrong"

| Prototype | Rule | Case: wrong value absent from every input, correct value never seen |
|---|---|---|
| `trace_claude.py:176-186` | AGENT_ERROR iff the **correct reference** was visible before the step | `undetermined/INPUT?` |
| `trace_oc.py` (§6), `trace_pi.py` (§6), `traceback_demo.py` (Codex) | AGENT_INTRODUCED / ORIGINATED iff the **wrong token** is absent from prior observations | agent fault |
| DECISION / repo §4, literature R3 | `provable` = verifier flip on the reconstructed state; R3 adds "could have known" | depends on which conjunct is enforced |

A 2×2 over (wrong value in inputs?) × (correct value in inputs?) has four cells. The prototypes agree only on
(yes, no) = input fault. They disagree on:
- (no, no): a hallucination;
- (yes, yes): conflicting sources, where the agent picked the wrong one.

The design must fix all four cells explicitly. It must also say where the "correct reference" comes from for claims
that have none (a `text must_not` check has no correct value) [INF].

### 1.3 "Mutating calls run serially" vs concurrent sub-agents

- capture-claude §2.6 says mutating calls in one message ran serially, so "per-call Pre/Post workspace diffs are
  therefore attributable within one actor". It also leaves concurrent sub-agents as [INF].
- [RUN `critic/claude/out/A_base/hooks.jsonl`] Two foreground `Agent` calls (`run_in_background:false`) in one
  message ran concurrently:

  ```
  639 ms   PreToolUse Agent toolu_main_1_0 / toolu_main_1_1 (same ms)
  680/697  SubagentStart a8896e3c / a2c89927
  748 → 2820 ms  sub b Bash window      776 → 2840 ms  sub a Bash window   (overlap ≈ 2 s)
  ```

- Together with Codex (parallel calls and parent/child overlap) and pi (parallel by default), **every platform has an
  ordinary path to overlapping mutation windows**. Workspace diffs are exact only when windows do not overlap
  (committed recorder field: `concurrent_with`).

### 1.4 "Join at SessionEnd" vs SessionEnd not guaranteed

capture-claude §0.3 and §7.4 recommend doing the transcript join at `SessionEnd` ("complete in 6/6 runs").
capture-codex §9 and the committed `finalize.py` also key on it. My counter-evidence is in §3.3: Claude skipped
`SessionEnd` in 2 of 2 runs with a still-running background task. For pi, SIGINT and SIGKILL give no
`session_shutdown` [RUN-sheet]. The design needs a launcher-side finalizer. Hooks are only an early copy.

### 1.5 "Sub-agents are fully attributable" (Claude) vs the shell

That holds for hook-visible tool calls only. [RUN `critic/claude/out/A_base/proj/env_*.txt`] The Bash env of the main
agent and of both sub-agents is identical:

```
CLAUDECODE=1  CLAUDE_CODE_CHILD_SESSION=1  CLAUDE_CODE_ENTRYPOINT=sdk-cli  CLAUDE_CODE_EXECPATH=/opt/claude-code/bin/claude
CLAUDE_CODE_SESSION_ID=<session uuid>  CLAUDE_PID=<pid>  CLAUDE_EFFORT=medium  CLAUDE_CODE_SESSION_ATTENDED=0
CLAUDE_CODE_MESSAGING_SOCKET=/tmp/cc-socks-0/<pid>.sock  CLAUDE_CODE_MESSAGING_TOKEN=<redacted>
```

There is no agent id and no call id, so anything the shell does cannot be tied to a sub-agent from its environment.

### 1.6 Smaller inconsistencies

- **Where `transcript_path` points inside a sub-agent differs by platform.** On Claude it is the *main* transcript; on
  Codex it is the *sub-agent's* rollout. A single normalizer must not assume either [RUN-sheet, both].
- **"Served" vs "requested" model is named differently in each sheet.**
  - Claude: the transcript's `message.model` is what the server reported, but the agent writes it.
  - Codex: hooks carry the requested slug.
  - OpenCode: the configured model.
  - pi: both `model` and `responseModel`.

  Only a proxy *observes* the served model. The committed `claimed:` prefix is correct for all four. The repo sheet's
  word "observed" should be reserved for the proxy.
- **The literature sheet calls all four capture paths "native hooks"** (§1.7). pi uses an in-process extension and
  OpenCode a plugin. Both are order-dependent and co-resident code can subvert them [RUN-sheet pi m1/m2, OpenCode S12].
  The novelty sentence should say "native hooks, plugins or extensions".
- **Rewriting or denying `run_in_background`** (capture-claude §7.2) changes agent behaviour. It is avoidable given
  §3.1.

---

## 2. [RUN] claims re-checked

| Claim (sheet) | Check | Verdict |
|---|---|---|
| 177/177 hook `tool_use_id`s found in transcripts (Claude §0.1) | recounted over `claude/out/*/hooks.jsonl` and every transcript | **holds**: 177/177 over 12 runs. Caveat the sheet omits: ids are mock-built `toolu_<role>_<k>_<i>`, unique by construction. Two sub-agents sharing one role script would collide. Real-API uniqueness is [INF]. The same applies to Codex (`call_<n>_<i>`) and OpenCode. Only the pi sheet states this |
| The WebFetch side call in the haiku sub-agent used `claude-opus-5-5` (Claude §4) | `T3_haiku/mock/requests.jsonl` n=4 | **holds**. Addition: the side call **carries the sub-agent's `x-claude-code-agent-id`** (`aca4166c…`) but no tool id. It is attributable to the actor by header and to the step only by time window (Pre/Post of the WebFetch). The same was seen in `T1` (n=4) |
| Transcripts are subject to a 30-day retention sweep ([RUN], Claude §0.10) | the evidence is one OTel `retention_sweep{period_days:"30"}` event | **over-tagged**: deletion was not observed. It should be [RUN event] + [DOC] |
| Mutating calls run serially, so diffs are attributable (Claude §0.7) | §1.3 | **true only within one actor** |
| Hooks run outside the Codex sandbox (Codex §0.9, evidence: env var) | [RUN `critic/codex/runs/CX_base`] hook `/proc/self/status`: `Seccomp: 0, NoNewPrivs: 0` (15/15 hook calls). Shell tool (root and sub-agent): `NoNewPrivs: 1, Seccomp: 2, Seccomp_filters: 1` | **now [RUN]** |
| OpenCode: a bash `>>` append shows up as a patch on the bash turn (§0.2) | `S1_single/db_dump.json`: `bash call_7_0` and `patch{files:[…/brief.md]}` sit in the same message `…1LjOfOac` | **holds** |
| pi: payload sha256 matches the mock body 7/7 (§0.11) | recomputed from `g2/trace/trace-12590.jsonl` against a compact re-serialization of `mock/req_*.json` | **holds, 7/7**. It matched a compact re-serialization, not raw bytes; a proxy must hash the same canonical form [INF] |
| pi tracer record counts 130 / 55 (§0.11) | recounted | **holds** |
| repo P1–P7, R, T | ran against the WIP tree | **not re-run**. The code has since been committed and changed. P3 re-confirmed on committed code (§1.1) |

---

## 3. Missing facts the design needs, with status

### 3.1 Attributing files changed by shell commands (goal 1, and the base of goal 2)

| Fact | Status |
|---|---|
| Native per-call or per-actor id inside the shell process | **Claude: none** [RUN §1.5]. **Codex: `CODEX_THREAD_ID` = the actor's thread**, root = session id, sub-agent = child thread id; `CODEX_SESSION_ID` = root [RUN `CX_base/ws/env_*.txt`]. **OpenCode: `shell.env` injects any var** (e.g. `VACANT_CALL_ID`) [RUN-sheet S1/S2]. **pi: `PI_SESSION_ID`/`PI_SESSION_FILE`/`PI_MODEL`/`PI_PROVIDER`**, no call id [RUN-sheet] |
| Does a PreToolUse `updatedInput` tag (`export VACANT_CALL_ID=<id> VACANT_ACTOR=<agent>; <cmd>`) reach the process? | **Claude: yes** for main, both sub-agents and the background Bash [RUN `B_rewrite`, `E_rw2`]. **Codex: yes, but only with `permissionDecision:"allow"`**. Without it the rewrite is **silently ignored**: 0 tagged lines, no error [RUN `CX_rewrite` vs `CX_rewrite2`] |
| What is recorded after a rewrite | **Claude**: the transcript `tool_use.input` and the history replayed to the model keep the **model's original** command; `PostToolUse.tool_input` shows the **executed** one [RUN `B_rewrite`]. **Codex**: rollout `function_call.arguments` and the replay are original; rollout `item_completed.item.command` = `["/bin/bash","-lc","export VACANT_CALL_ID=call_1_0 …"]`, i.e. executed; `PostToolUse.tool_input` is executed [RUN `CX_rewrite`]. So the tag is invisible to the model, but it splits "model-issued" from "executed" args, and the record must keep both |
| **Side effect of tagging on permissions (Claude)** | [DOC `doc_hooks.md` L1816]: "Claude Code evaluates permission rules … against the input your hook returns". [RUN] With allow rule `Bash(echo:*)` in default mode: `echo hi` **ran** untagged (`K_n2_norw`) and was **denied** once tagged (`L_n2_rw2`; `permission_denials` lists `export VACANT_CALL_ID=toolu_main_2_0 …; echo hi`). With the tag plus `"allow"`, every command the user's rules deny **ran** (`H_narrow_rw1` vs `F_narrow_norw`). ⇒ Tagging either breaks narrow allow-lists or silently widens them. It must not be the default. On Codex, tagging requires `"allow"`, which [INF, from `understand/agent-codex.md` §3] auto-approves under interactive approval policies |
| OS-level tracing available? | This Linux container: `strace` present; `fanotify_init` succeeds (root, full CapEff); no bpftrace or perf [RUN]. **Exhibition OS: unknown.** CLAUDE.md's `~/Library/...` paths suggest a Mac dev machine, and none of `strace`, fanotify or bwrap exists on macOS [INF] |
| Does OS tracing attribute shell writes per call without touching the input? | **Yes (Linux)** [RUN `M_strace_norw`, `attr_by_argv.py`]. Claude runs each command as `/bin/bash -c -l "<shell snapshot> … eval '<command, ' → '"'"'>' < /dev/null && pwd -P >\| <tmp>/claude-<pid>-cwd"`. Matching the hook's `tool_input.command` (quote-transformed) in that argv, then walking `clone` parents from each `openat(O_WRONLY\|O_CREAT…)`, gave `env_main.txt→toolu_main_0_0`, `env_suba.txt, a.txt→toolu_suba_0_0`, `env_subb.txt, b.txt→toolu_subb_0_0`, `env_bg.txt, late_after_exit.txt→toolu_main_2_0`: **7/7, including concurrent sub-agents and background Bash**. With the tag instead of argv matching it is also 7/7 [RUN `C_strace`]. Caveats: identical commands from concurrent actors yield a candidate set; relative paths need cwd tracking (Claude persists `cd` via the `pwd -P` file); `-s` must be large (at `-s 400` the command was cut off and 0/7 matched) |
| Cost of `strace -f` | 4.78 s (`B_rewrite`) → 7.8 s (`C_strace`) and 7.65 s (`M_strace_norw`) on the same scenario, n=1 each [RUN]. Not measured on long sessions |
| Writes by in-process tools (Write/Edit) and MCP servers | Write/Edit are in hooks with path and patch [RUN-sheets]. MCP server processes are children of the agent, so OS-level they attribute to the server pid, and to a call only by time window. Ambiguous under concurrency [INF] |
| Network effects inside the shell (curl POST, git push) | not captured by any sheet. `strace -e network` would show `connect()` but not content [INF]. **Unknown** |

### 3.2 Identifying actors and sub-agent definitions (goals 1 and 3)

| Fact | Status |
|---|---|
| Actor id for each step | Covered by the sheets: Claude hook `agent_id`/`agent_type` + `subagents/agent-<id>.meta.json{toolUseId, parentAgentId, spawnDepth}`; Codex `agent_id` = thread + child `session_meta.parent_thread_id`; OpenCode `session.parent_id` + task `metadata.sessionId`; pi content join over `details.results[].messages` [RUN-sheets] |
| Where definitions live (for a per-definition reputation cell) | **Claude** [DOC `doc_sub-agents.md` L165-183]: identity = frontmatter **`name`** (the file name is irrelevant); directories scanned **recursively**; 5 scopes (managed > `--agents` JSON > project `.claude/agents/`, walking up with the nearest winning > `~/.claude/agents/` > plugin `agents/`, where the scoped id is `plugin:sub:name`). **Codex** [SRC `core/src/config/config_tests.rs:8523-8790`]: roles are **`.toml`** in `$CODEX_HOME/agents/` and `<repo>/.codex/agents/`, or `[agents.<role>] config_file=…`. **OpenCode** [SRC binary strings `"{agent,agents}/**/*.md"`, `config/paths.ts:23-43`]: under `Global.Path.config` (`~/.config/opencode`), every `.opencode` walking up to the worktree, `~/.opencode`, `OPENCODE_CONFIG_DIR`, plus JSON `agent` keys. **pi example** [SRC `examples/extensions/subagent/agents.ts:76-146`]: identity = frontmatter `name`; `getAgentDir()/agents` (`~/.pi/agent/agents`) and the nearest `.pi/agents` walking up |
| Committed lookup | `actors.definition_of` checks only `<ws or ~>/{.claude/agents, .opencode/agent(s), .codex/agents, .pi/agents}/<name>.md` [SRC `trace/actors.py:57-79`]. It misses all Codex roles (.toml), OpenCode global XDG and nested definitions, Claude name≠file / subfolders / `--agents` / plugins / managed, and the pi user directory. It then labels these `builtin:<name>`, which is **wrong, not just coarse** |
| Observed alternative | Hash what the actor **received**. **Claude**: the sub-agent transcript has `attachment.type:"prompt_snapshot"{systemPrompt:[…]}` [RUN `claude/out/T1/…/subagents/agent-a11a26b3ab8aa86ea.jsonl`]. **pi**: child `sections.addendum` in `details.results[].messages` [RUN-sheet]. **Codex**: child rollout `session_meta.base_instructions` + developer messages [RUN-sheet]. **OpenCode**: system prompt not persisted; needs `experimental.chat.system.transform` [RUN-sheet] |
| Cross-platform built-in collisions | `builtin:general-purpose` (Claude), `builtin:general` (OpenCode), `builtin:default` (Codex) are distinct strings, but all share the per-stream decay clock logic of §1.1 [RUN probe] |

### 3.3 Detecting unrecorded changes and sealing the session (goal 1 completeness)

| Fact | Status |
|---|---|
| Does `SessionEnd` always fire? | **Claude `-p`: no.** [RUN `A_base`, `A_base2`] With a `run_in_background` Bash (`sleep 8; …`) still running: `Stop` at ≈3.2 s, `result` success, then after ≈5.5 s the task is killed (stream-json `task_notification{status:"stopped", tool_use_id:"toolu_main_2_0"}`), rc 0, and **no `SessionEnd`**. Controls: no background task (`A_nobg`) and a task that finishes in 1 s (`A_shortbg`) both fire `SessionEnd`. The kill is **not in the transcript**; its tail is `stop_hook_summary`, `last-prompt`, `cost-state` |
| Early warning | Claude `Stop` carries `background_tasks:[{id:"bev0i4i22", type:"shell", status:"running", description, command}]` [RUN]. The id equals `PostToolUse.tool_response.backgroundTaskId` [RUN-sheet]. So Vacant can tell at Stop that SessionEnd may not come |
| Do background processes outlive the agent? | **Claude `-p`**: no. Killed, no orphan after 12 s (`ps`) [RUN]. **Codex exec**: killed at turn end (`exit_code:-1`) [RUN-sheet S5]. **pi**: orphans survive SIGINT/SIGKILL (`late.txt`) [RUN-sheet]. **OpenCode**: shell `&` jobs and background sub-agents **unknown** (not run) |
| Consequence for the committed code | `trace/capture.py:146-151` does, on `session_end` only: `seal_transcript` (hash, and `models_from_transcript`, the only source of Claude's per-step model), `rec.close` (the final `unrecorded_change` scan) and `_outcome`. `finalize.py` is also launched from that hook [SRC]. A session with a background task at exit loses all four. The launcher (`vacant do` / `run.py`) does not finalize after exit [SRC grep] |
| Human or other-process edits during the session | Workspace diffs charge them to the next step [INF, all sheets]. Tracing the **agent's process tree** (strace) or reading the writer pid (fanotify) separates agent writes from other writers [INF; the mechanism was RUN in §3.1]. Unverified end-to-end |
| Changes outside the workspace | Workspace scans miss them. `strace` shows absolute-path opens (e.g. `~/.claude/shell-snapshots/…`) [RUN `M_strace_norw`] |

### 3.4 Telling input and requirement faults from agent faults (goal 3)

| Fact | Status |
|---|---|
| Implicit instruction inputs (Claude) | [RUN `D_claudemd`] `CLAUDE.md` containing a marker: `InstructionsLoaded{file_path:"…/CLAUDE.md", memory_type:"Project", load_reason:"session_start"}` fired **once** (not per sub-agent; it carries no content, so hash the file then). The transcript `attachment.type:"instructions"` appears in the main transcript **and both sub-agent transcripts**. The marker is in **8/8** model request bodies, inside a `<system-reminder>` in the first user message. `trace_claude.py`'s `inputs_seen` covers only tool results [SRC], so a value that came from CLAUDE.md would be classed as agent-authored |
| Same for the others | Codex: AGENTS.md in rollout `world_state` / developer messages [RUN-sheet]. pi: system `sections` persisted [RUN-sheet]. OpenCode: **not persisted**, needs a hook [RUN-sheet]. None of the four tracers reads them [SRC] |
| Tool-internal model as a third actor | The Claude WebFetch summary comes from a side model: session small/fast model, not the actor's model [RUN-sheet T3]. An error introduced there is neither "external input" nor "agent". No fault class exists for it in the repo taxonomy (`agent/input/requirement/suite_or_verifier/harness/infra/unattributable`) [INF]. The raw page is only visible at the proxy or in OTel |
| Who authorized a step (human approval vs config) | Claude OTel `tool_decision`: `{decision:"accept", source:"config"}` ×15 in `T8_otel` [RUN]. Codex OTel `codex.tool_decision{decision, source:"Config"}` [RUN-sheet]. OpenCode `permission.replied` (live only) [RUN-sheet]. pi has no native permissions. **Interactive human-approval values: unknown on all four** (all runs were headless) |
| Mid-session human instructions | Recorded on all four (UserPromptSubmit / user message / `input`) [RUN-sheets]. The tracers check only the initial prompt or task (pi, OpenCode) [SRC]. A later human message that introduced the wrong value is **unhandled** [INF] |
| Where the check's "correct value" comes from | Only some intake verifiers return one (e.g. `csv_total` evidence `recomputed`) [SRC repo sheet]. `ClaimResult` has no structured location or expected value. **Design gap, unknown** |
| Conflicting sources (both wrong and right visible) | **Design gap**: no sheet decides it (§1.2) |
| Compaction or truncation changing what the model saw | Not triggered on any platform. **Unknown.** Proxy request bodies are the only ground truth; Claude OTel bodies are cut at 61439 chars [RUN-sheet] |

### 3.5 Other facts the design needs

- **OpenCode's DB holds `credential` and `account` tables** [RUN: they exist in every `db_dump.json` schema, with 0
  rows in the isolated homes]. `run_oc.py` dumps *every* table. On a real `$XDG_DATA_HOME` the same reader would copy
  the user's stored provider credentials into Vacant's evidence. The reader must whitelist
  `session/message/part/event/project`.
- **Claude requests carry `metadata.user_id` = `{"device_id":"<64-hex>","account_uuid":"","session_id":…}`**
  [RUN `T1/mock/bodies/003.json`]. A proxy-side record stores a stable device identifier. This is a privacy item for
  exhibition logs (CLAUDE.md delivery rule 6).
- **Hook payloads have no timestamps.** Ordering under concurrency relies on Vacant's own receive time plus
  `tool_use_id` [RUN-sheets].
- **Real-API fidelity** is unknown on every platform: id uniqueness, thinking redaction or encryption, served-model
  headers, the Codex v2 encrypted hand-off. Everything above is L-fake.

---

## 4. Verified additions (new facts this critique established)

1. [RUN] Committed `trace/actors.py` shares one decay clock across platforms (`stream="main"`). Claude's mean went
   0.55 → 0.52 after 400 Codex events. Codex's branch is `codex/0`.
2. [SRC] The four trace-back prototypes use two incompatible definitions of agent fault. `trace_claude.py` labels a
   sourceless wrong value `undetermined/INPUT?`.
3. [RUN 2/2] Claude `-p` skips `SessionEnd` when a background Bash is still running at exit, and kills that task after
   about 5.5 s. Controls fire `SessionEnd`. `Stop.background_tasks[]` gives an early warning. The kill is absent from
   the transcript.
4. [RUN] With `SessionEnd` absent, the committed transcript seal, per-step model extraction, final gap scan and
   outcome are all skipped [SRC `capture.py:146-151`].
5. [RUN] Two foreground Claude sub-agents in one message run concurrently, and their Bash windows overlap by about 2 s.
6. [RUN] The Claude Bash env is identical for the main agent and sub-agents: `CLAUDE_CODE_SESSION_ID` and
   `CLAUDE_PID`, but no agent or call id.
7. [RUN] Codex shells carry `CODEX_THREAD_ID` = the actor's own thread (root or child) and `CODEX_SESSION_ID` = the
   root.
8. [RUN] Codex hooks run unsandboxed (`Seccomp 0/NoNewPrivs 0`); Codex shell tools run sandboxed (`Seccomp 2/NoNewPrivs 1`).
9. [RUN] A PreToolUse `updatedInput` tag reaches main, sub-agent and background processes on Claude, and main and
   sub-agent processes on Codex. The transcript, rollout and model replay keep the original command; PostToolUse
   (and Codex `item_completed.command`) show the executed one.
10. [RUN] Codex ignores `updatedInput` without `"allow"`, silently.
11. [RUN] On Claude, the tag prefix makes a narrow allow rule stop matching (`echo hi` denied). `"allow"` bypasses
    denying rules. So tagging is unsafe as a default.
12. [RUN] On Linux, `strace -f` plus matching the command inside the `bash -c` argv attributes 7/7 shell-written files
    to the exact `tool_use_id`, across concurrent sub-agents and a background Bash, without modifying the input.
    Overhead was about +3 s on a 4.8 s run.
13. [RUN] `strace` and fanotify are usable in this container. bpftrace and perf are absent.
14. [RUN] `CLAUDE.md` reaches every model request, sub-agents included. `InstructionsLoaded` fires once with the path
    and no content. `instructions` attachments sit in every transcript. No tracer counts it as an input.
15. [RUN] The Claude WebFetch side call carries the calling sub-agent's `x-claude-code-agent-id`, with no tool id.
16. [RUN] The Claude sub-agent transcript contains `prompt_snapshot`, so its delivered definition can be hashed.
17. [SRC/DOC] Real definition locations differ from what `actors.definition_of` checks: Codex `.toml` roles, OpenCode
    `~/.config/opencode/{agent,agents}/**`, Claude and pi identity by frontmatter `name`, and Claude's 5 scopes.
18. [RUN-sheet] Re-checks: Claude 177/177 (mock-constructed ids), the OpenCode bash patch, pi sha 7/7 and pi record
    counts hold. The Claude "30-day sweep" is over-tagged as [RUN].
19. [RUN] OpenCode's DB contains `credential`/`account` tables, which a "dump all tables" reader would copy.
20. [RUN] Claude requests carry a stable `metadata.user_id.device_id`.

## 5. Remaining unknowns

1. The exhibition machine's OS. On macOS there is no strace, fanotify or bwrap; the substitutes (`fs_usage`,
   EndpointSecurity) need root or an entitlement.
2. OpenCode: lifetime of background sub-agents and shell `&` jobs after `run` exits; whether `permission.replied` and
   plugin events are lost at exit.
3. Plugin order when a Vacant plugin comes from `OPENCODE_CONFIG_CONTENT` while global and project plugins also exist
   (the sheet's [INF]).
4. Human-approval provenance in interactive mode, on all four platforms.
5. Effect of compaction or pruning on "what the model saw", on all four.
6. Claude `--resume`/`--continue`, and OpenCode and pi session continuation: does a second session keep the actor and
   the chain?
7. Network side effects of shell commands: no channel records their content.
8. MCP-server-process writes under concurrency: time-window attribution only.
9. Identical commands issued concurrently by two actors: argv matching yields a candidate set. Is `concurrent_with` +
   `candidate_set` enough for the exhibition narrative?
10. Where the "correct reference" comes from for non-numeric claims, and the rule for conflicting sources (§1.2).
11. The fault class for a tool-internal side model (WebFetch summarizer) and for co-resident extension or plugin
    mutation.
12. The strace/fanotify cost on long sessions, and hook latency at scale (no sheet measured either).
13. Real-API fidelity: id uniqueness, thinking redaction, served-model headers, the Codex v2 encrypted hand-off.

## 6. Reproduce

```
cd scratchpad/accountability/critic/claude
python3 run_probe.py A_base                  # concurrency + env + bg killed + no SessionEnd
python3 run_probe.py A_nobg nobg             # control: SessionEnd fires
python3 run_probe.py B_rewrite rewrite shortbg
python3 run_probe.py C_strace rewrite strace shortbg && python3 attr_strace.py out/C_strace/strace.out "$PWD/out/C_strace/proj/"
python3 run_probe.py M_strace_norw strace shortbg   && python3 attr_by_argv.py out/M_strace_norw
python3 run_probe.py D_claudemd claudemd nobg
python3 run_probe.py K_n2_norw narrow2 echoonly ; python3 run_probe.py L_n2_rw2 narrow2 rewrite2 echoonly
python3 run_probe.py F_narrow_norw narrow nobg  ; python3 run_probe.py H_narrow_rw1 narrow rewrite nobg
cd ../codex
python3 run_probe.py CX_base scen_env.json "Dump env. Delegate the sub task to a helper."
REWRITE=1 python3 run_probe.py CX_rewrite  scen_env.json "Dump env. Delegate the sub task to a helper."
REWRITE=2 python3 run_probe.py CX_rewrite2 scen_env.json "Dump env. Delegate the sub task to a helper."
cd ../repo && PYTHONDONTWRITEBYTECODE=1 VACANT_HOME=$PWD/vh /home/user/Vacant/.venv/bin/python probe_actorbook.py
```
