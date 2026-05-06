# 5-minute thesis-defence demo script

**Goal:** show that a residency-form layer (vacants) on top of A2A / MCP
gives us a working *responsibility surface* -- identity + behaviour +
reputation that survives substrate change. Use the dashboard.

Open the dashboard before the talk:

```bash
uv run streamlit run src/vacant/mvp/dashboard.py
```

---

## 0:00 -- 0:30  Opening claim (don't click anything yet)

> "An LLM agent is not the unit of accountability. The agent runs on
> rented compute -- when the bill stops, the entity dissolves. The
> *vacant*, by contrast, is a residency form: identity (Ed25519
> keypair), continuity (signed logbook), behaviour (system prompt +
> tool whitelist), substrate (which LLMs it accepts), runtime, and a
> halo it carries everywhere. This dashboard demos the 6 components
> across 4 scenarios."

---

## 0:30 -- 1:30  Scenario 1: `law_firm` (composite + closed children)

1. Sidebar -> **情境**, pick **law_firm**, click **執行**.
2. Point to the events table:
   - 30 `delegate` events from the parent into the two LOCAL sub-vacants.
   - At the bottom: `closed_children_remained_local: True`.
3. Sidebar -> **網路**, scroll to `parent`:
   - F ~ 0.79, R ~ 0.79 (composite earns from successful delegation).
   - The two sub-vacants are LOCAL -- they have no public halo.

> "The composite is the only public face. The children are closed-by-
> default (CLAUDE.md §Closed children). Their reputation lives inside
> the composite's audit trail, not on the public registry."

---

## 1:30 -- 2:30  Scenario 4: `self_replication` (lineage + graduation)

1. Sidebar -> **情境**, pick **self_replication**, click **執行**.
2. Point to the events table:
   - 4 `spawn` events at ticks 30 (D1) / 50 (D2) / 80 (D3) / 120 (D5).
   - 1 `graduation` event at tick 180.
3. Sidebar -> **血緣**:
   - 5 unique keypairs (root + 4 children).
   - Lineage depth = 2.
   - D2 子代是否畢業: 是.
4. Open `result.metrics["d2_keypair_preserved"]` -> `True`.

> "Graduation is a visibility-flag flip, not an entity upgrade. Same
> keypair, same logbook -- the child's history continues. Lineage,
> not the individual vacant, is the subject of 'infinite evolution'
> (THEORY_V5 §4.3)."

---

## 2:30 -- 3:30  Scenario 2: `code_review` (reputation diverges + sniping defence)

1. Sidebar -> **情境**, pick **code_review**, click **執行**.
2. Sidebar -> **網路**, view the 5 reviewers:
   - Top 2: F ~ 0.87, 0.83 (≥ 0.8).
   - Bottom: F ~ 0.34 (≤ 0.4).
3. Sidebar -> **對抗**:
   - 環路被檢出 → 加權後信號: ~0.000 (bumped almost not at all).
   - 未被檢出 → 加權後信號: ~0.004 (the un-flagged review).

> "The same-controller signal does not stop a colluding ring from
> *trying*. It downweights the contribution by the max-strength
> signal. This is the cost-raising-not-preventing framing -- attackers
> can keep paying identity capital, but each round they spend more."

---

## 3:30 -- 4:30  Scenario 3: `multilingual_translation` (cross-substrate)

1. Sidebar -> **情境**, pick **multilingual_translation**, click **執行**.
2. Open `result.metrics`:
   - `polyglot_factual_claude` ~ 0.68, `polyglot_factual_gpt` ~ 0.61
     -- the *same vacant* has different posteriors per substrate.
   - `n_substrate_specific_posteriors`: 7.

> "A vacant declares a `substrate_spec`. The reputation system tracks
> per-(vacant, substrate) posteriors -- a translator who works well
> on Claude but poorly on GPT-4o has two distinct reputations. The
> portability_factor bonus rewards vacants that genuinely serve
> multiple substrates."

---

## 4:30 -- 5:00  指標 page + closing

1. Sidebar -> **指標**:
   - Walk the 8 metrics. Highlight **signature_verify_throughput**
     (~16k verifications/sec on a laptop) and **registry_consistency**
     (100% under concurrent writers).

> "Eight metrics. Each maps to a thesis claim. Run from `MockSubstrate`
> for bit-exact CI; swap to `AnthropicSubstrate` for the live demo.
> The dashboard, the integration test, and the dispatch are wired to
> the same scenarios -- if a scenario regresses, CI catches it before
> the demo does."

---

## Backup: the dashboard didn't open

```bash
uv run python -m vacant.mvp.demo --scenario=self_replication | jq '.metrics'
```

Quick CLI fallback that shows the same lineage + graduation metrics
without needing Streamlit.
