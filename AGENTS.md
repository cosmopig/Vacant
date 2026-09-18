# AGENTS.md — Vacant integration contract for coding agents

> Machine-facing. Written so a coding agent can wire Vacant into a pipeline **without
> asking a human**. Everything below is either a signature you can call, an invariant
> you can falsify, or a boundary that says the thing you want is *not* guaranteed.
> Companion index: [`llms.txt`](llms.txt). Human-facing overview: [`README.md`](README.md).

```
package        vacant-network        (PyPI)     import name: vacant
version        0.7.0
python         >= 3.11
runtime deps   cryptography>=42, mcp>=1.26,<2, jsonschema>=4.21
license        MIT
repository     https://github.com/cosmopig/Vacant
```

---

## 0. One paragraph

**Vacant is not a mandatory layer wrapped around an agent, and it is not another agent
framework. It is a receiving desk: a delivery without a verifiable receipt is not accepted.
Because it looks only at the deliverable and does not care how the agent ran, output from
any framework can be fed into it — you keep your existing agent.**

It runs the customer's own **executable acceptance tests** against a candidate, decides
*ship or refuse* on the result, and signs every attempt — including the failed ones — into
an append-only Ed25519 hash chain that anyone holding the public key can re-verify offline.
It does not make the agent better at writing code. It makes what the agent did
**checkable after the fact**, and it refuses to accept things that do not pass.

Enforcement lives at **acceptance time**, not execution time. Making Vacant the single exit
on a machine takes containers, ACLs or egress policy — the deployment layer's job, not
Vacant's. This is an existing pattern rather than one invented here: supply-chain security
does the same with **in-toto / SLSA / Sigstore**, where an artifact without a valid
attestation is rejected at intake.

The word used throughout is **accountability**, not *trust*. The classical definitions
(Gambetta 1988, Mayer 1995) put "acting without monitoring" into the necessary conditions
for trust, and monitoring is the entire content of this system. If you are writing copy
about Vacant, do not call it a trust layer.

---

## 1. What is enforced, and what is only advice

**Read this before claiming Vacant "wraps" anything.** Vacant is not automatically
binding just because it is installed. Whether it can be bypassed depends entirely on
which of four shapes you deploy.

In reference-monitor terms (Saltzer & Schroeder 1975), Vacant satisfies **tamper-proof**
and **small enough to be verified**, and does **not** satisfy **complete mediation**. That
is the unavoidable consequence of being optional, not a defect — and it is why the honest
word is *receiving desk*, not *mandatory layer*.

| Shape | Entry point | Binding on the agent? |
|---|---|---|
| **Library** | `vacant.agent.Vacant` (`vacant/agent.py:51-103`) | **No — voluntary.** `self.brain` is a public attribute. Code that does not call Vacant simply does not involve Vacant. |
| **MCP tool** | `vacant.mcp_server` (`vacant/mcp_server.py:184-210`) | **No — persuasion only.** The `delegate` tool docstring says "THE PREFERRED PATH". A model that ignores the tool is not intercepted, and nothing detects that. |
| **Controller** | `vacant.controller.VacantFirstController.delegate_then_run` (`vacant/controller.py:304-530`) | **Yes — for the subprocess it spawns itself.** It obtains a verified delivery first, and only then execs the downstream agent with `shell=False`. |
| **Harness owns the loop** | e.g. `ops/gain/r530/openwork_arms.py:642-696` | **Yes — the harness *is* the loop.** The agent has no path that skips the gate. ⚠ This is the shape **we** use for experiments, not a recommended integration: it means writing the loop yourself, so you cannot use an off-the-shelf agent. |

Verbatim honest boundary from `vacant/controller.py:7-8`, which nothing in this file may
be read as softening:

> 保證只涵蓋透過本 controller 啟動的子行程；無法阻止同一 OS 使用者繞過本命令直接執行
> agent。需要強制全機唯一出口時，仍須容器、ACL 或 egress policy。
>
> *(The guarantee covers only child processes launched through this controller. It cannot
> stop the same OS user from running the agent directly instead. A machine-wide single
> exit requires containers, ACLs, or egress policy.)*

**What *is* unconditional: the intake check itself cannot be routed around.**
`vacant/receipt.py` plus `controller.verify_delivery` **recompute five sha256 digests**
(request, task, tests, answer, trust card), verify the Ed25519 signature, compare
`chain_head` / `stream_id` / `branch_id` against the chain as it stands **right now**,
require every review to be bound to this exact delivery and answer, and only then
`policy.admit`. The launch right is claimed with `os.O_EXCL` (`vacant/controller.py:372`),
so **a receipt is consumable exactly once**. Anything that reaches the desk without a
receipt that survives all of that is rejected.

**Design rule that follows:** if the property you need is "the agent *cannot* ship
unverified work", you must use the controller or own the loop, **and** put an OS-level
boundary around it. If you use the library or MCP shapes, the honest description is
"the agent's verified work is accountable", not "the agent is constrained".

---

## 1a. What an outside party can check without trusting us

The point of an accountability layer is that its own claims are checkable. These four need
no cooperation from us:

| Claim | Command or file | Why it settles the question |
|---|---|---|
| The receipt chains were not altered | `python3 ops/gain/replay/verify_run_receipts.py --selftest`, then `--glob 'runs/g_r532_*'` | The self-test runs negative controls first, so the verifier is shown to catch a broken chain before it is pointed at real ones. R532: 86 chains, 3,895 entries, 0 failures. |
| The tasks were not cherry-picked | `docs/BANKS_HOWTO.md`, `runs/INDEX.md` | Bank sha256 is pinned; date windows and known-bad tasks are listed. |
| The conclusions are not the analyzer's invention | `runs/g_*/rows.jsonl` | One row per task per arm. `deliv = accepted AND meets_demand`. Recount it yourself. |
| We are not hiding our mistakes | `examples/verdicts.py`, and §7 H-0 below | Refuted claims are kept. So are the gaps we found in our own audit. |

---

## 2. Install and smoke-test

```bash
pip install vacant-network
python -c "import vacant; print(vacant.__version__)"
vacant --help                 # console script
```

Zero network, zero model calls, no clone required. `pip install vacant-network` pulls
30 packages (`mcp` accounts for most of them; `cryptography` and `jsonschema` are the
rest).

---

## 3. Sixty-second integration

Two independent pieces. Use either alone.

### 3a. The gate — run the customer's acceptance tests

```python
from vacant.checks import run_python_check

tests = "assert solve([1, 2, 3, 4]) == 6\nassert solve([]) == 0\n"
candidate = agent_writes_some_code()

ok = run_python_check(candidate, tests, allowed_entry_points=("solve",))
if not ok:
    # refuse, or feed the failure back and retry within a fixed budget
    ...
```

`run_python_check` runs the **test code and the candidate code in two separate
processes** and talks between them over stdin/stdout with a nonce-tagged, literal-only
RPC (`vacant/checks.py:577-600`, `444-457`). The candidate does not receive the test
source at all — see invariant I-2.

### 3b. The receipt — sign every attempt into a chain

```python
from vacant.identity import Identity, PublicIdentity
from vacant.logbook import Logbook

me   = Identity.generate()
who  = PublicIdentity(vacant_id=me.vacant_id, pub=me.pub)
book = Logbook()

book.append("attempt", {"draft": sha, "visible_ok": False}, me, ts_ms=t0)
book.append("attempt", {"draft": sha2, "visible_ok": True},  me, ts_ms=t1)
book.append("shipped", {"accepted": True, "draft": sha2},    me, ts_ms=t2)

book.save(Path("receipts.ndjson"))
assert Logbook.load(Path("receipts.ndjson")).verify_chain(who)
```

Append the **failed** attempts too. A chain that only contains successes is a chain that
answers no interesting question.

---

## 4. Public API surface

Import name is `vacant`. 50 modules; the ones below are the ones an integrator calls.
Everything else is either internal or experiment infrastructure.

### Core — works standalone, no `ops/` checkout, no network

| Module | What it is for |
|---|---|
| `vacant.identity` | Ed25519 keypair + `vacant_id`; on-disk keystore. |
| `vacant.logbook` | The append-only signed hash chain. `stream_id` = genesis hash. |
| `vacant.checks` | Two-process acceptance sandbox + check-spec compiler. |
| `vacant.suitespec` | **Acceptance suites are data, not code**: entry point + literal `(args, expected)` + comparison flags, plus a deterministic renderer. |
| `vacant.suitegauge` | Gauge for a suite: reference solution must pass **and** every known-bad stub must be rejected. |
| `vacant.envelope` | Signed `Envelope` / `ReviewEnvelope`, replay guard. |
| `vacant.checkpoint` | Checkpoint certification + retro-audit; checkpoints form their own chain. |
| `vacant.canonical` | The single serialization used for every signature. Change it and every chain in the world breaks. |
| `vacant.record` | `RECORD_SPEC` evidence-pack pack/check (excludes `identity.key`). |
| `vacant.research` | McNemar, bootstrap, Holm–Bonferroni, TOST, exact Wilcoxon, power. |
| `vacant.entrycost` | Mechanism **simulation** (no model). Anything rendered from this must be labelled as simulation. |

### Multi-party — needs a criterion injected (see §7, H-5)

| Module | What it is for |
|---|---|
| `vacant.peerexec` | k independent executors each run the suite and sign their own chain; verdict names *which key* dissented. |
| `vacant.auditor` | Deterministic re-audit (sha256 sampling, sandbox, provable-fault). |
| `vacant.registry` / `vacant.reputation` / `vacant.router` | Discovery index, 5-dimensional Beta reputation, on/off routing switch. |

### Product path

| Module | What it is for |
|---|---|
| `vacant.controller` | `VacantFirstController` — the only shape that is binding on a spawned subprocess. |
| `vacant.ecosystem` | Resident ecosystem: route → generate → verify → cross-review → receipt. |
| `vacant.mcp_server` | MCP server exposing `delegate` / `trust_card` / `report`. Advisory (see §1). |
| `vacant.cli` | `vacant` console script. |

### Signatures you will actually call

```python
# vacant.checks
run_python_check(candidate_code: str, test_code: str, *, timeout: float = 8,
                 allowed_imports: tuple[str, ...] = (),
                 allowed_entry_points: tuple[str, ...] = ()) -> bool
run_python_capture(candidate_code: str, probe_code: str, *, timeout: float = 8,
                   allowed_imports=(), allowed_entry_points=()) -> str | None
compile_check(spec: dict) -> Verifier            # Verifier(answer: str) -> bool
project_checked_answer(answer: str, spec: dict) -> str

# vacant.identity
Identity.generate() -> Identity
Identity.save(dir_path: Path, *, passphrase: bytes | None = None) -> None
Identity.load(dir_path: Path, *, passphrase: bytes | None = None) -> Identity
PublicIdentity.from_hex(vacant_id: str, pub_hex: str) -> PublicIdentity
PublicIdentity.verify(message: bytes, signature: bytes) -> bool

# vacant.logbook
Logbook.append(etype: str, payload: Any, identity: Identity, *, ts_ms: int,
               branch_id: str | None = None) -> LogEntry
Logbook.verify_chain(who: PublicIdentity) -> bool
Logbook.head() -> str
Logbook.stream_id() -> str | None                # genesis hash; None on an empty chain
Logbook.save(path: Path) -> None
Logbook.load(path: Path) -> Logbook
verify_genesis(entry_json: dict, who: PublicIdentity) -> str | None

# vacant.suitespec
validate(obj: Any, *, entry_point: Any = <unbound>) -> SuiteSpec
render(spec: SuiteSpec) -> str                   # deterministic: same spec -> same bytes
from_task(task: Mapping, *, compute=None, timeout_s: float = 30.0) -> Conversion

# A suite as a mapping. `v` is REQUIRED and its only legal value is 1.
# Omitting it raises SuiteSpecError(code="bad_version:None").
{"v": 1,                       # spec version -- required, must be exactly 1
 "dialect": "mbpp",            # "mbpp" | "lcb"; default "mbpp"
 "entry_point": "solve",       # must equal task["entry_point"]
 "tests": [{"args": "[1, 2]",  # literal list/tuple of POSITIONAL args, as source text
            "expected": "3"}], # any literal, as source text
 "cmp": {}}                    # mbpp only: atol / set_equivalent / regex_predicate
# SuiteSpecError carries `.code` (machine-readable, goes on the chain and into
# Selection.refusal_reason) and `.hint` (human-readable). Compare `.code`, never str(exc).

# vacant.suitegauge
gauge_suite(check_code: str, reference: str, broken_stubs: Sequence[str] = (), *,
            entry_point: str | None = None, runner: CheckRunner | None = None,
            timeout_s: int = 10) -> GaugeOutcome        # .ok is the only verdict
broken_stub(entry_point: str | None) -> str
# CheckRunner = (code, check_code, entry_point, timeout_s) -> (ok: bool, message: str)

# vacant.peerexec
Executor.new(executor_id: str, *, probe: Probe = sandbox_probe) -> Executor
Executor.attest(task: Mapping, draft_code: str, *,
                suite: SuiteSpec | Mapping | bytes, ts_ms: int | None = None) -> Attestation
# task REQUIRES "entry_point" (the function name the suite must exercise) and normally
# carries "task_id". The entry point belongs to the TASK, not to the suite: the suite's
# own entry_point is only CHECKED against it. A task without that key raises
# SuiteSpecError(code="entry_point_unbound") before any sandbox run -- even when the
# SuiteSpec you passed in does carry entry_point="solve".
verify_attestation(att, roster, *, task_id=None, draft_sha256=None,
                   suite_sha256=None, render_sha256=None) -> tuple[bool, str]
form_verdict(attestations, roster, *, task_id, draft_sha256, suite_sha256,
             quorum: int = 1, gauged_suites=None, render_sha256=None) -> Verdict
select_by_quorum(task, drafts, executors, *, suite, roster=None, quorum=None, ...) -> Selection
# drafts: Sequence[tuple[str, str]] -- each element is (code, worker_id) IN THAT ORDER.
#   [0] the candidate's Python source; [1] the name of the worker that produced it.
# Swapping them is not a type error: every "draft" then fails the suite, the panel agrees
# unanimously, and you get refused=True / shipped_index=None with three chains that all
# verify -- indistinguishable from the mechanism correctly rejecting bad work.
# select_by_quorum applies a cheap HEURISTIC shape check and raises
# peerexec.DraftOrderError when the order looks reversed. It has false negatives
# (see its docstring); the signature above is the only guarantee.
commit_suite_with_gauge(book, identity, *, task_id, suite, nonce, reference,
                        entry_point, broken_stubs=None, runner=None, ...) -> LogEntry
challenge_rerun(task, draft_code, panel, original, *, suite, ...) -> Challenge

# vacant.controller
VacantFirstController.delegate_then_run(*, task: str, tests: dict, risk: str = "normal",
        launch: ArgvTemplate | None = None, cwd=None, env=None,
        timeout: float = 900, require_agent_success: bool = True) -> ControllerResult

# vacant.research
mcnemar_exact(b: int, c: int) -> float
holm_bonferroni(pvals: list[float]) -> list[float]
tost_equiv_boot(diffs, delta, *, alpha=0.05, n_boot=2000, seed=0) -> dict
wilcoxon_signed_rank_exact(diffs, *, alpha=0.05) -> dict
mcnemar_power(n: int, p_disc: float, psi: float, *, alpha=0.05) -> float
```

### Check-spec grammar (`compile_check`, and the MCP `tests` argument)

```text
{"type": "equals",      "value": "<exact answer>"}
{"type": "contains",    "value": "<substring>", "ignore_case": true}
{"type": "regex",       "pattern": "<regex>"}
{"type": "json_schema", "schema": {...}}
{"type": "run_python",  "code": "assert solve('ab') == 'ba'"}
```

Only `equals`, `json_schema` and `run_python` are strong enough to gate an agent launch.
`contains` and `regex` are for exploration and will not carry a delivery.

---

## 5. Where to intercept

Pick the **narrowest** layer that gives you the property you need.

1. **You only want a pass/fail bar on a candidate** → call `run_python_check` directly.
   No identities, no chain, no configuration. This is most integrations.
2. **You want an audit trail of attempts** → add a `Logbook` and append every attempt.
   Nothing else has to change; the chain is independent of how the candidate was produced.
3. **You want the suite itself to be tamper-evident** → express the suite as a `SuiteSpec`
   and commit it with `commit_suite_with_gauge` before any candidate is generated. The
   executor then renders the code it runs *from the spec*, so a supplier cannot hand you
   a "test" that is really a program.
4. **You want k independent parties to agree** → `peerexec.select_by_quorum`, each executor
   with its own key and its own chain. Disagreement names the dissenting **key**.
5. **You want the agent to be unable to ship unverified work** → `VacantFirstController`,
   plus an OS boundary. See §1.

### What the agent has to cooperate with

- Return **code that defines the declared entry point**. The gate calls
  `entry_point(*args)`; it does not read prose.
- Tolerate refusal. A budget that runs out is a **refused delivery**, and a refusal counts
  as a failure in every rate Vacant reports. An integration that silently ships the last
  candidate on exhaustion has removed the only thing the gate does.
- Not receive the hidden tests. If you keep a held-out set, it must never enter a prompt,
  a retry message, or a lesson. (Repo rule A4: feedback may abstract to the *shape* of a
  failure, never quote test data.)

---

## 6. Verifiable invariants

Each one is falsifiable; the check is given.

- **I-1 — The chain detects edits and deletions in the middle.** Changing a payload,
  removing an interior entry, or removing the genesis entry all make `verify_chain`
  return `False`. Check: tamper with `entries[k]` for `0 < k < len-1` and re-verify.
- **I-2 — The candidate structurally cannot read the test code.** Test code lives in the
  runner process, candidate code in a separate worker; they communicate over a
  nonce-tagged literal-only RPC (`vacant/checks.py:577-600`, `444-457`). Verbatim comment
  at `ops/gain/gain_run.py:957`: *"the candidate worker cannot see this test code"*. This
  is a structural property, not a blocklist. Check: a candidate that tries
  `open(__file__)` or `os._exit(0)` to fake success does not pass — the quickstart in
  `README.md` demonstrates the `os._exit(0)` case.
- **I-3 — Self-reported success is never taken on faith.** The ecosystem runs the verifier
  itself (`vacant/ecosystem.py:531`), and the controller then runs it **again**,
  independently, before any launch (`vacant/controller.py:299-300` →
  `GateRejected("local objective re-check rejected the delivered answer")`).
- **I-4 — "Not measured" is not "passed", and it is written as code.**
  `"all_pass": bool(total > 0 and passed == total)` (`ops/gain/r530/acceptance.py:272`) —
  a suite that reported zero tests fails. Same shape in the library: `GaugeOutcome.ok`
  requires `n_broken >= 1`, so an empty set of known-bad stubs cannot satisfy
  `all_rejected` vacuously (that would be fail-open).
- **I-5 — The suite gauge is two-sided.** `ok` requires *both* that the reference solution
  passes *and* that every known-bad stub is rejected. One-sided gauges miss "accepts
  everything" and "rejects everything" respectively.
- **I-6 — Rendering is deterministic.** `suitespec.render(spec)` is a pure function of the
  spec, so `render_sha256` is comparable across machines and across parties.
- **I-7 — Refusal happens for real.** R532, 836 tasks: the gated arm accepted 811 of 836
  and **refused 25**; the loop arm refused 68. Refusal is in the denominator of every
  rate reported.

---

## 7. Honest boundaries — what is **not** guaranteed

These are part of the specification. Do not paraphrase them into something more
comfortable, and do not drop them when quoting a number.

- **H-0 — A claim we made and have had to retract.** We stated that R532 was
  "V/GT 43/43 CLEAN", meaning hidden-test separation was verified across the run. **That was
  false.** `ops/gain/harness_vgt_audit.py:746` is `if arm not in VARIANTS: continue`, and
  `ops/gain/harness_arms.py:65` sets `VARIANTS = ("HPI", "HOC", "HMIX")` — so the `OFF` and
  `CONFORM` arms were **never scanned**, and every block's `per_arm` contains only
  `{'HMIX': N}`. The accurate statement is "**the H-MIX arm is 43/43 CLEAN; the other two
  arms are unaudited**". A retroactive sweep of 179 archived runs is in progress and its
  result is not in. Until it is, nothing may claim V/GT is clean across arms. This entry is
  kept deliberately: finding and publishing a hole in our own audit is the evidence that
  accountability is workable, in a way no performance number is.
- **H-1 — Premise, overriding everything below.** The whole mechanism assumes the
  requirement can be compiled into an executable acceptance suite. Where it cannot,
  there is no free referee and the system degrades into "ask a model", which is the thing
  that measured badly. (Verbatim source:
  `DECISION_20260903_R440P_CONFORMANCE_GATE.md` §五-1.)
- **H-2 — Passing the suite is not meeting the requirement.** Verbatim from
  `vacant/suitegauge.py:30-33`: blocking known-bad stubs proves only that the suite does
  not pass everything; it **does not** prove the suite covers the real requirement. A
  suite with three asserts deleted down to one still passes the gauge. Measured: in R532,
  of the 811 deliveries the gate accepted, **120 (14.8%) passed the visible suite and
  still failed the hidden check**. The gate roughly halves false delivery (25.2% ungated
  → 14.8% gated); it does not remove it.
- **H-3 — The chain gives integrity, not completeness.** Integrity means nothing was
  altered. **Completeness — nothing is missing — is not provided.** `verify_chain`
  (`vacant/logbook.py:168-195`) checks sequence continuity, `prev_hash` linkage, and
  per-entry signatures. There is **no length commitment and no external anchor**, so a
  valid prefix verifies. The literature's name for this is a **truncation / omission
  attack** (Ma & Tsudik 2009). Reproduced:

  ```
  original 5 entries   -> verify_chain = True
  drop the last 2      -> verify_chain = True     <- NOT detected
  remove an interior 1 -> verify_chain = False
  edit an interior one -> verify_chain = False
  drop genesis         -> verify_chain = False
  ```

  Two consequences that must be stated with it:
  - **The checkpoint chain has the same hole, one level up.**
    `verify_checkpoint_chain` (`vacant/checkpoint.py:144-155`) only walks
    `prev_checkpoint_sig` backwards and requires the first to be null, so **dropping the
    last few checkpoints leaves a chain that fully verifies**. Reproduced: 4/4 pass,
    dropping the last 2 still passes, removing an interior one fails, removing the first
    fails.
  - **Signing the entry count into every entry does not fix it.** `seq` already *is* the
    count, and every entry of a truncated prefix stays self-consistent. A length commitment
    only works if it is **exogenous** — held by another party, or timestamped before the
    truncation could have happened.

  If you need truncation-evidence, you must publish heads externally (`Logbook.head()`)
  or countersign — Vacant does not do it for you.
- **H-4 — A signature identifies a key, not a person, and not the truth.** A receipt proves
  "this key said this, and it has not been altered since". It does not prove the statement
  is true, and it does not prove who holds the key (`vacant/peerexec.py:117-120`). On the
  product path the receipt is signed by the **delivering party itself**
  (`vacant/ecosystem.py:641-642`), and the private key is a plaintext PEM readable by the
  same OS user (`vacant/body.py:160` calls `identity.save` with no passphrase). Key
  custody is a deployment assumption; software cannot *prevent* forgery by root.
- **H-5 — The published wheel has no default acceptance criterion.** `suitegauge.default_runner`
  and `peerexec.sandbox_probe` delegate to `ops.gain.gain_run.meets_demand`, which ships
  only in the git repository, because it carries the G-experiment's own sandbox import
  allow-list and `infra_void` semantics — the library must not assert a policy on your
  behalf, and a second copy of the acceptance criterion is exactly the drift both
  docstrings forbid. Calling them without `ops/` raises
  `vacant.suitegauge.OpsRunnerUnavailable` with instructions. **Inject instead**:
  `gauge_suite(..., runner=my_runner)`, `Executor.new(..., probe=my_probe)`.
- **H-6 — The sandbox is application hardening, not an OS security boundary.** It blocks
  the common `os._exit(0)`, same-file hidden-test reads, and process/file APIs, under
  `python -I`, clean env/cwd, CPU limit and wall timeout. It is **not** a complete
  malicious-code boundary. Untrusted code belongs in a container, gVisor, or a separate VM.
  `vacant/checks.py` has no working Windows sandbox branch (posix only).
- **H-7 — Majority vote has a mathematical ceiling.** k executors tolerate at most
  ⌊(k−1)/2⌋ corrupted ones. Past that the mechanism **inverts** — the corrupted majority
  names the honest executors as dissenters — and **the mechanism cannot tell which side of
  the threshold it is on**.
- **H-8 — The renderer and the sandbox are trusted inputs.** Trust is *relocated*, not
  eliminated. A renderer bug makes k machines wrong **consistently**, and the dispute rate
  stays 0.
- **H-9 — Sybil resistance raises cost, it does not prevent.** Minting a fresh identity
  currently costs nothing. This is a property of the mechanism, not a tunable parameter.
- **H-10 — An evidence pack is self-consistent, not true.** `SHA256SUMS` **detects**
  post-hoc tampering; it does not **prevent** it.
- **H-11 — The reconciliation is same-origin.** The three reconciliation rules in
  `ops/gain/replay/verify_run_receipts.py` (verdict count == row count, task_id sets equal,
  attempt count >= verdict count) compare **two records written by the same process**. They
  catch asymmetric omissions, which is to say **bugs**; they cannot catch both sides failing
  to write together, which is to say **malice**. Real reconciliation requires at least one
  end to be held by a party with different interests. That is not in place, and no number in
  this file should be read as if it were.
- **H-12 — Numbers below come from local quantized models on five fixed task sets.** They
  do not transfer to another model, another harness, another budget, or another corpus
  without being re-run.

---

## 8. Common mistakes

| Wrong | Right | Why |
|---|---|---|
| `VACANT_ENDPOINT=http://host:8765` for the experiment runner | `VACANT_GAIN_API=http://host:8765/v1/chat/completions` | Three different variables with three different shapes. `VACANT_GAIN_API` (`ops/gain/brain_cline.py:134`) is the **full path**, not a base URL. `VACANT_ENDPOINT` (`vacant/substrate.py:171`) is a base URL for `vacant.substrate`. `VACANT_MCP_BASE` + `VACANT_MCP_MODEL` + `VACANT_MCP_API` drive the CLI, and `VACANT_MCP_API` must be exactly `responses` or `openai`. |
| Gating on `{"type": "contains", ...}` | `equals` / `json_schema` / `run_python` | `contains`/`regex` are exploration checks. They are not strong enough to authorize a delivery or an agent launch. |
| Recording only successful attempts | Append every attempt, failures first | A success-only chain cannot answer "how many tries did this take" or "did it ever ship something wrong". |
| Treating a passing chain as proof the work is correct | Treat it as proof the record is unaltered | H-4. |
| Treating a passing chain as proof nothing is missing | Publish heads, or countersign | H-3: integrity is not completeness; truncation is not detected. |
| Adding an entry count to each entry to stop truncation | An **exogenous** length commitment | `seq` is already the count; a truncated prefix stays self-consistent. |
| Treating `verify_run_receipts.py` reconciliation as an independent audit | Treat it as a same-origin self-check | H-11: both sides are written by the same process. |
| Calling Vacant a "mandatory layer" | "receiving desk": a delivery without a verifiable receipt is not accepted | It does not satisfy complete mediation; a machine-wide single exit is the deployment layer's job. |
| `pip install vacant` | `pip install vacant-network` | `vacant` on PyPI is an unrelated DNS tool by another author. The **import** name is still `vacant`. |
| Calling `Executor.new(id).attest(...)` from the wheel and catching `ImportError` | Inject a probe: `Executor.new(id, probe=my_probe)` | H-5. **Once the task validates**, the exception is `OpsRunnerUnavailable` and its message contains the fix. Validation runs first, so a malformed `task`/`suite` raises `SuiteSpecError` before the probe is ever reached. |
| Calling `attest` / `select_by_quorum` with a task that has no `entry_point` | `task = {"task_id": ..., "entry_point": "solve", ...}` | The entry point belongs to the task; the suite's copy is only checked against it. Otherwise `SuiteSpecError(code="entry_point_unbound")`, *even if the suite declares one*. |
| Writing a suite mapping without `"v": 1` | `{"v": 1, "dialect": "mbpp", "entry_point": ..., "tests": [...], "cmp": {}}` | `v` is the spec version and 1 is its only legal value; omitting it gives `bad_version:None`. No compatibility conversion, by rule 6. |
| `select_by_quorum(task, [(worker_id, code), ...], ...)` | `select_by_quorum(task, [(code, worker_id), ...], ...)` | Both are `str`, so the wrong order type-checks. The result is a clean, fully-signed **refusal** -- the same shape the docs teach you to trust. The built-in check is a heuristic with false negatives. |
| Reading `str(exc)` off a `SuiteSpecError` to branch on | `exc.code` | `str()` also carries the human hint and may be reworded; `.code` is the wire-facing string that goes on the chain. |
| Treating `vacant bench` output as a measurement without reading its exit code | Non-zero exit means **nothing was measured** (`infra_void`) | A failed model call is neither a right answer nor a wrong one. `bench` refuses to print any comparison when either arm measured zero cells, and prints the void count separately when it is partial. |
| Shipping the last candidate when the budget runs out | Refuse, and count the refusal as a failure | Ship-on-exhaustion deletes the only thing the gate does. |
| Feeding hidden-test text back into a retry prompt | Feed the *shape* of the failure | Repo rule A4. Quoting held-out test data invalidates the measurement. |
| Calling it a "trust layer" | "accountability layer" | See §0. |
| Citing `runs/_analysis_*` as source data | Cite `runs/g_*/rows.jsonl` | The 136 `_analysis_*` directories are **derived** from the raw rows; citing them feeds a conclusion back to itself. Read `runs/INDEX.md` before citing any run. |

---

## 9. Machine-readable facts

Stable schema. `results` values are point estimates with their denominators; every entry
carries the file that produced it.

```json
{
  "schema": "vacant.facts/1",
  "package": {
    "pypi_name": "vacant-network",
    "import_name": "vacant",
    "version": "0.7.0",
    "requires_python": ">=3.11",
    "runtime_dependencies": ["cryptography>=42", "mcp>=1.26,<2", "jsonschema>=4.21"],
    "license": "MIT",
    "console_script": "vacant",
    "module_count": 50,
    "test_files": 78
  },
  "terminology": {
    "use": "accountability",
    "never_use": ["trust layer", "trusted layer", "信任", "信任層"],
    "reason": "Gambetta 1988 / Mayer 1995 put 'acting without monitoring' into the necessary conditions for trust; monitoring is the whole system.",
    "scope": "user-visible output and prose. Identifiers are API surface and keep their names: trust_dir, trust_card, trust_on, --trust, and the trust/ directory.",
    "enforced_by": "tests/test_cleanroom_blockers.py -- scans every argparse help text and the stdout/stderr of demo, init, up and bench"
  },
  "enforcement": {
    "model": "receiving desk, not a mandatory wrapper and not an agent framework",
    "framework_agnostic": "operates on the deliverable, not on how the agent ran",
    "recommended_shapes": ["library", "mcp_tool", "controller"],
    "not_recommended_for_integrators": "harness_owns_loop -- that is our experiment shape; it requires writing your own agent loop",
    "enforced_at": "acceptance time: a delivery without a verifiable receipt is not accepted",
    "not_enforced_at": "execution time",
    "intake_check": "vacant/receipt.py + controller.verify_delivery: 5 sha256 recomputed, Ed25519 verified, chain_head/stream_id/branch_id compared against the live chain, os.O_EXCL makes a receipt consumable once",
    "prior_art": ["in-toto", "SLSA", "Sigstore"],
    "reference_monitor_Saltzer_Schroeder_1975": {
      "tamper_proof": true,
      "small_enough_to_verify": true,
      "complete_mediation": false
    },
    "library": "voluntary",
    "mcp_tool": "advisory",
    "controller": "binding on its own spawned subprocess only",
    "harness_owns_loop": "binding",
    "machine_wide": "requires container / ACL / egress policy (vacant/controller.py:7-8)"
  },
  "chain_guarantees": {
    "integrity": true,
    "completeness": false,
    "truncation_attack": "not detected -- truncation/omission attack, Ma & Tsudik 2009",
    "also_affects": "vacant/checkpoint.py:144-155 verify_checkpoint_chain",
    "seq_does_not_help": "seq is already the entry count; a truncated prefix stays self-consistent",
    "fix": "an exogenous length commitment -- held by another party, or timestamped before the truncation"
  },
  "reconciliation": {
    "tool": "ops/gain/replay/verify_run_receipts.py",
    "same_origin": true,
    "catches": "asymmetric omissions (bugs)",
    "does_not_catch": "both sides omitting together (malice)",
    "requires": "at least one end held by a party with different interests -- not in place"
  },
  "banned_phrasings_for_results": [
    "replication failed", "effect disappeared", "equivalent", "tied",
    "majority supports", "replication stable", "improvement", "the loop is useless"
  ],
  "results": [
    {
      "id": "R460R.conform_vs_off",
      "claim": "executable acceptance gate + resample, versus one-shot",
      "model": "gemma-4-12b-it-qat", "bank": "LCB v2", "n": 120,
      "delta_pp": [14.17, 18.33, 17.50, 19.17, 18.97],
      "note": "five same-task replications; p_raw < 0.002 each, NOT multiplicity-corrected",
      "source": "DECISION_20260912_R460R_FABLE_AUDIT_REPLICATIONS.md"
    },
    {
      "id": "R460R.hmix_vs_conform",
      "claim": "feedback loop, versus equal-budget resample",
      "model": "gemma-4-12b-it-qat", "bank": "LCB v2", "n": 120,
      "delta_pp": [5.83, 4.17, 0.83, 2.50, 4.31],
      "holm_significant": "0/5",
      "status": "not established",
      "source": "DECISION_20260912_R460R_FABLE_AUDIT_REPLICATIONS.md"
    },
    {
      "id": "R529.hmix_vs_conform",
      "claim": "feedback loop, versus equal-budget resample, across banks",
      "model": "gemma-4-12b-it-qat", "n": 716, "banks": 4, "real_sources": 3,
      "delta_pp_pooled": 1.12, "holm_p_adj": 0.341,
      "status": "not established",
      "source": "DECISION_20260912_R529_FABLE_AUDIT_CROSS_BANK.md"
    },
    {
      "id": "R529.hmix_vs_off",
      "claim": "feedback loop, versus one-shot, across banks",
      "model": "gemma-4-12b-it-qat", "n": 716,
      "delta_pp_pooled": 7.96, "holm_p_adj": 2.0e-8,
      "source": "DECISION_20260912_R529_FABLE_AUDIT_CROSS_BANK.md"
    },
    {
      "id": "R532.conform_vs_off",
      "model": "qwen3.8-27b Q4_K_M non-thinking", "n": 836, "banks": 5,
      "delta_pp_pooled": 7.89, "ci95_pp": [5.36, 10.04], "p": 3.04e-9,
      "caveat": "outside the pre-registered family; p is NOT multiplicity-corrected",
      "source": "ops/gain/r532/results_r532.json#secondary_outside_family"
    },
    {
      "id": "R532.hmix_vs_off",
      "model": "qwen3.8-27b Q4_K_M non-thinking", "n": 836,
      "delta_pp_pooled": 4.67, "ci95_pp": [1.75, 7.38], "p": 0.0015, "holm_p_adj": 0.0030,
      "source": "ops/gain/r532/results_r532.json#primary"
    },
    {
      "id": "R532.hmix_vs_conform",
      "model": "qwen3.8-27b Q4_K_M non-thinking", "n": 836,
      "delta_pp_by_set": [-5.83, -5.19, -16.67, -1.28, -0.54],
      "delta_pp_pooled": -3.23, "ci95_pp": [-5.52, -0.75], "p": 0.0101,
      "quotable_state": "RULED_OUT",
      "quotable_sentence": "rules out a practical gain of >= +2 pp for the loop over equal-budget resample, on these 836 tasks",
      "not_quotable_state": "EFFECTIVE",
      "caveat": "the pre-registered state table had no direction guard, so a significant result in the OPPOSITE direction was labelled EFFECTIVE. AMEND1 forbids quoting EFFECTIVE. 'Reverse and significant' has no pre-registered state, so no 'the loop is harmful' conclusion is drawn.",
      "source": "DECISION_20260917_R532_STRONGER_MODEL_PREREG.md#AMEND1"
    },
    {
      "id": "R532.premise_not_supported",
      "claim": "the run's premise 'a stronger model' is NOT supported by its own data",
      "off_arm_deliv_pp": {"27b": 74.8, "12b": 75.2},
      "lcb_sets_all_worse_pp": [-9.2, -9.6, -3.7],
      "reading": "what was measured is 'a different model', not 'a stronger model'; two points and non-monotone",
      "source": "DECISION_20260917_R532_STRONGER_MODEL_PREREG.md#AMEND2"
    },
    {
      "id": "R532.false_delivery",
      "claim": "the gate halves false delivery; it does not remove it",
      "n": 836,
      "ungated_accepted": 836, "ungated_false_delivery": 211, "ungated_false_pp": 25.24,
      "gated_accepted": 811, "gated_false_delivery": 120, "gated_false_pp": 14.80,
      "gated_refusals": 25, "loop_refusals": 68,
      "source": "runs/g_r532_*/rows.jsonl (accepted AND NOT meets_demand)"
    },
    {
      "id": "R532.integrity",
      "blocks": 43, "rows": 2508, "infra_void": 0,
      "vgt_clean": {"arm": "HMIX", "blocks": "43/43",
                  "arms_never_scanned": ["OFF", "CONFORM"],
                  "cause": "ops/gain/harness_vgt_audit.py:746 `if arm not in VARIANTS: continue`, VARIANTS = (HPI, HOC, HMIX)",
                  "do_not_claim": "V/GT clean across arms",
                  "status": "retroactive sweep of 179 archived runs in progress, result not in"},
    "hidden_test_fingerprints": 199019,
      "receipt_chains": 86, "receipt_entries": 3895, "receipt_failures": 0,
      "reproduce": "python3 ops/gain/replay/verify_run_receipts.py --glob 'runs/g_r532_*'",
      "source": "git commit 746c3d7"
    }
  ],
  "red_lines": [
    "KS-1: no prompt template may contain 'you are responsible' / 'you will be punished' wording; arm templates are verbatim identical. Executable guard: vacant.memory.assert_ks1_clean",
    "A4: feedback may abstract to the shape of a failure; quoting held-out test data is forbidden. Guard: lesson_leaks_test_data",
    "All I/O lands as JSONL; retry x4; infra_void rows are dropped, never back-filled",
    "Memory is never shared across arms; history-dependent behaviour must not be cached",
    "A demo may say 'you can see an improvement'; 'proves an improvement' is reserved for a pre-registered batch run"
  ],
  "denominators": {
    "HumanEval+": "156, not 164 (8 tasks excluded by the sandbox envelope)",
    "MBPP+": "371 of 378 (7 excluded by the resource envelope)",
    "LCB v2": 120, "LCB v3 medium": 135, "LCB v3 hard": 54
  },
  "reproduce": {
    "receipt_chains": "python3 ops/gain/replay/verify_run_receipts.py --glob 'runs/g_r532_*'",
    "hidden_test_separation": "python3 ops/gain/harness_vgt_audit.py --run <run> --bank <bank> --scope v2  # H arm only -- see H-0",
    "arbiter_self_test": "python3 ops/gain/analyze_r529.py --selftest && python3 ops/gain/analyze_r529.py --mutation-check",
    "r532_arbiter_self_test": "python3 ops/gain/r532/analyze_r532.py --selftest",
    "banks_howto": "docs/BANKS_HOWTO.md"
  }
}
```

---

## 10. If you are writing about Vacant

1. Every number carries its denominator and the premise in H-1.
2. `RULED_OUT` means "an effect of at least this size is excluded". It does not mean "no
   effect", and it is a **result**, not a failure.
3. Same sign across replications with none passing correction is **unresolved**, not
   negative, and not positive.
4. Never pool independent replications into one large `n` to manufacture significance.
5. A refusal counts as a failure. Rates whose denominator excludes refusals are not
   comparable to the ones here.
6. Before citing any run, task bank, or log, read [`runs/INDEX.md`](runs/INDEX.md): it says
   which entries are evidence, which are smoke or aborted, and which 136 `_analysis_*`
   directories are derived artefacts that must not be cited as source data.
