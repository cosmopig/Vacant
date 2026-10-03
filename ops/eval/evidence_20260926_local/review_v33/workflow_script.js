export const meta = {
  name: 'review-zero-config-v32-v33',
  description: 'Adversarially review the zero-config v3.2/v3.3 diff (check after the end, reminder provenance, error-stop note)',
  phases: [
    { title: 'Find', detail: 'three independent angles over git diff 5f3339df..HEAD' },
    { title: 'Verify', detail: 'reproduce or refute each finding' },
  ],
}

const CONTEXT = `
Repo: /home/user/Vacant. Review ONLY the change range: git diff 5f3339df..HEAD -- vacant_network tests ops/eval/gate3 ops/eval/local (commits "零設定 v3.2" 33634f62 and "v3.3" a2b4b0ee, plus render_run/split_ended helpers). Read the design in decisions/DECISION_20260926_ZERO_CONFIG_V3.md §七 and §八.
What changed:
- pi extension (vacant_network/adapters/agents.py PI_EXTENSION): tracks LAST_FINAL (last real turn had no tool results and stopReason "stop"), LAST_TEXT, LAST_STOP; session_shutdown sends final_answer/final_text and uses the stop timeout when "late"; agent_before_settle sends last_stop.
- hook (vacant_network/adapters/hook.py): _said_done_unchecked; session_end zero-config branch now also runs when a final answer came on the capped turn; _zero_stop passes error_stop.
- zerostop (vacant_network/trace/zerostop.py): ended() now runs the same delivery check after the end for BOTH a final answer on the capped turn and a cut-off run (_check_after_end), writing the normal delivery note with an "after the end" preface; _write_note gets a "Budget reminders" section (_reminded_writes) and an error-stop context line; stop()/_decide get error_stop.
Rules that must hold (from CLAUDE.md and the decision): nothing sent to the model changes (requests byte-identical to before when nothing is wrong; pushback text identical with/without error flag); failures never block the agent (any error ⇒ allow / write nothing); notes go only to Vacant's data folder; KS-1 (no "responsible/punished" wording) and no actor named in model-facing text; claims in notes must be literally true about the record; Claude Code / Codex / OpenCode paths must not change behaviour.
Do NOT modify files in the repo. Use scratch dirs under /tmp/claude-0/review_v33/ for any repro (create it). Do NOT touch docker, the proxy on port 18900, or anything under /tmp/claude-0/-home-user-Vacant/95e2b6b6-418f-504c-a59e-fd594ef13041/scratchpad/local (a preregistered batch is running there). Do not read credential files. Tests: /home/user/Vacant/.venv/bin/python -m pytest <files> -q ; node is available for driving the extension (see tests/test_zero_budget.py for a fake-pi driver).
Report only real defects with a concrete failing scenario (inputs → wrong output/crash/false statement). No style nits.`

const FINDINGS = {
  type: 'object',
  properties: { findings: { type: 'array', items: { type: 'object', properties: {
    title: { type: 'string' }, file_line: { type: 'string' },
    severity: { type: 'string', description: 'major | minor' },
    scenario: { type: 'string' }, fix: { type: 'string' },
  }, required: ['title', 'file_line', 'severity', 'scenario'] } } },
  required: ['findings'],
}
const VERDICT = {
  type: 'object',
  properties: {
    real: { type: 'boolean' }, severity: { type: 'string' },
    evidence: { type: 'string', description: 'what you ran or read, and what it showed' },
    affects_model_facing: { type: 'boolean', description: 'does it change anything the model receives' },
  },
  required: ['real', 'evidence'],
}

const ANGLES = [
  { key: 'paths', prompt: `Angle: correctness of the session-end paths. Walk every combination the hook can see at session_end and stop: aborted true/false, final_answer true/false, turn/budget present/absent/over budget, last review allow/continue/none, a prior "ended" event, observe mode, sub-agent sessions (parent_session_id), multiple sessions in one project, a new person request after a cut-off, reason=reload/new/resume/fork, a broken or set-aside chain, _run_child raising or timing out, a very large project. Find cases where a note is written that is false, a note is missing where the design says one is written, the check runs when it must not (e.g. it re-runs heavy work on every normal session end), an exception escapes, or state (rounds, state.json sessions, verified mark) is corrupted for the next request.` },
  { key: 'notes', prompt: `Angle: are the statements in the delivery note literally true about the record? Focus on _reminded_writes and the "Budget reminders" section, the "Vacant checked no value in it" condition, the step numbers it prints (e.fields "n" vs ordinal), the error-stop line, and the after-end prefaces. Build concrete records (use the Pi helper pattern in tests/test_zero_budget.py) where a line says something false: e.g. a file deleted after the reminder counted as "written", a write by a sub-agent, writes to several files, a nudge from a previous request, a reminder in another session of the same project, a deliverable not requested, numbers in the file that are checked vs the "one deliverable" condition, the error flag when the error turn was followed by more turns, pluralisation.` },
  { key: 'model_facing', prompt: `Angle: does anything the model receives change, or can the agent be blocked/slowed? Drive the real extension in node (fake pi as in tests/test_zero_budget.py) and the real hook. Check: the stop payload now includes last_stop — can it change the reason text or the action? Session_shutdown now may wait up to the stop timeout (600 s) in interactive pi when LAST_FINAL and TURNS>=BUDGET or ABORTED — can a person quitting pi (Ctrl-C / Esc then quit) be made to wait minutes, and in which realistic cases? Does the pi extension still parse and behave on older/newer event shapes (message missing, content string, toolResults undefined)? Any path in Claude Code / Codex / OpenCode hooks affected by the hook.py changes (e.g. payload fields final_answer/aborted from other agents)? Anything that breaks the "byte-identical when nothing is wrong" invariant.` },
]

phase('Find')
const results = await pipeline(
  ANGLES,
  a => agent(`${CONTEXT}\n\n${a.prompt}`, { label: `find:${a.key}`, phase: 'Find', schema: FINDINGS }),
  (r, a) => parallel((r && r.findings || []).map((f, i) => () =>
    agent(`${CONTEXT}\n\nIndependently reproduce or refute this finding. Build the smallest repro you can (real hook.handle / real node extension), or show from the code why it cannot happen. Default to real=false if you cannot reproduce it.\n\nFINDING: ${JSON.stringify(f)}`,
      { label: `verify:${a.key}:${i + 1}`, phase: 'Verify', schema: VERDICT })
      .then(v => ({ ...f, angle: a.key, verdict: v })))),
)
const all = results.flat().filter(Boolean)
log(`${all.length} findings, ${all.filter(f => f.verdict && f.verdict.real).length} reproduced`)
return { findings: all }
