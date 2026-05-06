# 5-minute demo presentation script

**Goal:** show that a residency-form layer (vacants) on top of A2A /
MCP gives us a working *responsibility surface* — identity + behaviour
+ reputation that survives substrate change. The five minutes are
sequenced so that each beat answers one open question from the prior:
"is this real network?" → "can my client actually use it?" →
"does the cost-raising defense actually fire?" → "does the lineage
claim hold up?"

Pre-flight (run before the audience walks in):

```bash
# Terminal 1 (live network demo)
vacant init alice
vacant init bob

# Terminal 2 (MCP external client)
# Claude Desktop already pointed at http://localhost:8443/mcp;
# `npx @modelcontextprotocol/inspector` ready as a backup.

# Terminal 3 (dashboard)
uv run streamlit run src/vacant/mvp/dashboard.py
```

---

## 0:00 — 0:30  Opening claim (don't click anything yet)

> "An LLM agent is not the unit of accountability. The agent runs on
> rented compute — when the bill stops, the entity dissolves. The
> *vacant*, by contrast, is a residency form: identity (Ed25519
> keypair), continuity (signed logbook), behaviour (system prompt +
> tool whitelist), substrate (which LLMs it accepts), runtime, and a
> halo it carries everywhere. The next four minutes show this
> running over real network, callable from any MCP client, defending
> against collusion, and surviving rotation in a way the lineage —
> not the individual — keeps."

---

## 0:30 — 1:30  Live network (A4) — *"is this real network?"*

Two terminals visible side-by-side.

**Terminal 1:**

```bash
vacant serve --port 8443 --name alice
```

The startup line prints `Vacant alice ready on http://0.0.0.0:8443`.

**Terminal 2:**

```bash
vacant call <alice_vid> capability/echo --endpoint http://localhost:8443
```

The response prints back, with its signature footer. Run it twice; the
second response shows a fresh nonce in the envelope.

> "This is a real HTTP roundtrip — `uvicorn` on the server side,
> `httpx` on the client side, signature-verified at both ends. There
> is no in-process shortcut. The integration test pinning this
> (`tests/integration/test_live_serve.py`) spawns the same two
> processes in CI."

(Leave Terminal 1 running — it's the vacant for the next beat.)

---

## 1:30 — 2:30  MCP external client (A3) — *"can my client use it?"*

Switch to **Claude Desktop** (or `npx @modelcontextprotocol/inspector`
as the backup).

1. Open the MCP server panel; alice should already be listed at
   `http://localhost:8443/mcp`.
2. Click `tools/list` → alice's capabilities show, derived from her
   `capability_card.capability_text`.
3. Invoke a tool. Claude Desktop prompts for substrate consent → you
   accept. Behind the scenes the vacant sends MCP
   `sampling/createMessage` back to the client; the client's LLM
   answers; the vacant signs the logbook entry.

Show the logbook entry on screen (Terminal 1's stderr or
`vacant demo --tail`):

```
[alice] CALL substrate=client-inherited:claude-desktop:claude-sonnet-4-6
        signed=ed25519:0x…
```

> "Substrate is a *resource*, not the *identity*. Alice has no
> `ANTHROPIC_API_KEY`. The brain came from the calling client; the
> vacant signed its own logbook entry; the substrate identity is
> recorded as `client-inherited:<caller>:<model>`, so reputation
> per-substrate works the same way it does for any other backend.
> ADR D017 pins the security model. This is what 'responsibility
> layer on top of MCP' literally means."

---

## 2:30 — 3:30  Adversarial seed-666 (B3) — *"does the defense fire?"*

Switch to the **dashboard** → sidebar **對抗** page.

1. Click **執行 adversarial (seed=666)**.
2. Watch the events stream: 10 vacants, 4 in a controller-ring, 6
   independent. ~200 mutual reviews unfold in the ring + cross-cluster.
3. After the run, the page shows:
   - same-controller signal on the 4-ring: `≥ 0.7`
   - ring → ring reviews: weight ≤ 0.5 of nominal
   - UCB ranking: non-ring vacants outrank the ring **despite** the
     ring's inflated raw scores

Toggle "show signal trace" → the heatmap reveals which review pairs
got downweighted and by how much.

> "Same-controller / same-substrate / same-stylo detection is **cost-
> raising, not preventing**. The ring still posts reviews; we don't
> ban them. We discount their contribution by the max-strength
> signal, with a `SAME_SIGNAL_DISCOUNT_FLOOR` floor (D015 §A) so a
> wrongly-flagged honest reviewer is never silenced. Attackers can
> keep paying identity capital — each round costs them more, the
> ranking holds."

---

## 3:30 — 4:30  Self-replication completeness (B4) — *"does lineage work?"*

Sidebar → **情境**, pick **self_replication**, click **執行**.

1. Watch the events stream: 4 spawns at ticks 30 (D1) / 50 (D2) / 80
   (D3) / 120 (D5), graduation at tick 180.
2. Sidebar → **血緣**: 5 unique keypairs, depth = 2, D2 child shows as
   *graduated*.
3. Open `result.metrics`:
   - `d2_keypair_preserved: True` — graduation was a visibility-flag
     flip, not a re-spawn (CLAUDE.md §Closed children).
   - `parent_drift_discount_after_epoch_5: 0.42` — STYLO discount
     stalled the parent's individual evolution, exactly as §4.3
     predicts.
   - `sunk_custody_attestation_count: 3` — after the parent transitions
     to SUNK, its heartbeat is still emitted as
     `{liveness: false, key_in_custody: true}` (THEORY_V5 §4.2). It
     cannot review (`can_review` = False) but it can still attribute
     lineage.
   - `child_clean_posterior: True` — the fresh D1 child after the
     parent stalls starts with an unburdened posterior; the lineage
     clock reset.

> "Individuals are mortal. Lineage evolves. STYLO discount bites the
> parent's self-evolution after epoch 5; a new D1 spawn resets the
> clock. The SUNK heartbeat keeps the keypair attestable so the
> lineage chain stays auditable even after the individual stops
> serving traffic. This is the load-bearing §4.3 mechanism — the
> claim that 'lineages evolve infinitely while individuals are
> mortal' is what these three numbers together attest."

---

## 4:30 — 5:00  指標 page + closing

Sidebar → **指標**.

- Walk the 8 metrics from `dispatch/P7_mvp.md` §3. Highlight:
  - **`signature_verify_throughput`** (~16k verifications/sec on a
    laptop) — the per-pair envelope chain is not a bottleneck.
  - **`same_controller_detection_rate`** — 100% on the seeded ring.
  - **`registry_consistency_under_concurrency`** — 100% across 50
    concurrent halo writers.

> "Eight metrics, four scenarios, one runbook. Live network in two
> terminals. MCP integration that needs no key on the vacant side.
> Same-controller defense that downweights without silencing.
> Lineage that survives individual death. The dashboard, the
> integration tests, and the dispatch all read the same `var/demo.db`
> event store — if a scenario regresses, CI catches it before the
> presentation does."

---

## Backup paths

If the dashboard crashes or the network demo dies on stage, drop to
the CLI:

```bash
# A4 fallback — events without the live network
vacant demo law_firm --tail

# A3 fallback — verify MCP wiring without Claude Desktop
npx @modelcontextprotocol/inspector --transport stdio -- \
  vacant serve --mcp --stdio --name alice

# B3 fallback — adversarial as JSON
vacant demo adversarial --seed=666 | jq '.metrics'

# B4 fallback — self-replication metrics
vacant demo self_replication | jq '.metrics'
```

Each backup is the same data path the dashboard would have rendered;
none of them need the GUI.
