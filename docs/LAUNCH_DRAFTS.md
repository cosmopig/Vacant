# Launch drafts

Ready-to-paste copy for the v0.2.0 (or v1.0) public launch. Order
below is **suggested launch order**, not chronological — landing in
this order rides each previous post's traffic into the next venue.

1. **Show HN** — Tuesday or Wednesday, 09:00 UTC (peaks the front-page window).
2. **Reddit r/LocalLLaMA + r/ClaudeAI** — same day, 4 hours after HN to ride the spike.
3. **Twitter/X thread** — same day, posted ~1h after Reddit.
4. **Bluesky** — same time as the X thread; same content, no need to stagger.
5. **Dev.to / Medium long-form** — 24-48h later, reflecting on the launch reception.

Substitute the actual release URL once tagged. None of the drafts
mention numeric metric thresholds — those drift; let the linked
README + tests speak for themselves.

---

## 1) Hacker News — Show HN

**Title (80-char limit):**

```
Show HN: Vacant – a responsibility layer for AI agents on top of A2A/MCP
```

**Body (HN doesn't allow markdown; use plain text):**

```
Hi HN — I built Vacant for a capstone project. It's a stand-alone "responsibility layer" that sits on top of A2A and MCP, the two transport protocols people are settling on for multi-agent comms.

The problem: A2A and MCP only specify *how agents talk*. Neither says anything about *who's accountable for what they say*. So when two LLM-driven agents collude to game a benchmark, or one gives a wrong answer, or the same name shows up in a new session — there's no native concept that says "this is the same agent, here's its history, here's what its track record costs to fake."

Vacant fills that gap. An agent that adopts the vacant residency form gets:

  - Ed25519 identity (numerical sameness across sessions)
  - An append-only signed logbook (what it said, in what order, signed)
  - A 5-dimensional Beta reputation per substrate (factual / logical / relevance / honesty / adoption), with STYLO-distance discount that bites self-evolution
  - Same-controller / same-substrate / same-stylo detection — explicitly framed as "cost-raising, not preventing", since Skalse 2022's impossibility theorem is assumed true rather than fought

The implementation is Python 3.12 + FastAPI + SQLite + pynacl. ~778 tests, mypy strict, MIT. There's an MCP server (`vacant serve --mcp`) that uses the calling client's LLM via `sampling/createMessage`, so the deployed vacant requires zero API keys of its own — the hosting client (Claude Desktop, OpenClaw, Hermes) supplies the brain.

Everything is in the README. Demo runs without an install:

  uvx --from git+https://github.com/cosmopig/Vacant vacant demo law_firm

I'd love feedback on the threat model and the reputation math. Three rounds of adversarial review with codex have signed off on the implementation; the open theoretical question is whether the 5-dim Beta posterior is still the right shape for adoption-style reviews.

Repo: https://github.com/cosmopig/Vacant
Theory writeup: https://cosmopig.github.io/Vacant/explain/theory/
```

**Posting notes:**
- HN allows one self-promo per author; no "Edit: …" updates after the first hour (adds `[edited]` flag, hurts ranking).
- Reply to every top-level comment within the first 90 minutes. Don't argue; thank, clarify, link.
- If the post falls below page 5 within 4 hours, do NOT re-submit. Wait two months.

---

## 2) Reddit — r/LocalLLaMA

Subreddit: https://www.reddit.com/r/LocalLLaMA/

**Title:**

```
[Project] Vacant — accountability layer for multi-agent LLM networks (MIT, ~778 tests, MCP-native)
```

**Body (Markdown, 300 words):**

```markdown
Hi LocalLLaMA — sharing **Vacant**, a stand-alone *responsibility layer* for multi-agent networks running A2A or MCP. It's not a framework; it's a layer any agent can adopt to gain identity, history, and reputation that survives across sessions and clients.

**The "why" in one paragraph:** when you wire two LLMs into an agent network and they collude to inflate a benchmark, the existing stack (LangGraph / CrewAI / AutoGen — all great frameworks) has no canonical answer for *who pays*. Vacant adds a layer that says: every agent carries an Ed25519 keypair, a signed append-only logbook, and a 5-dim Beta reputation per substrate. Reviews from same-controller pairs are detected and downweighted (we test ring-on-ring weight ≤ 0.5× indep weight under seed 666). STYLO-distance discount bites self-evolution at the *individual* level, but the *lineage* (parent_id chain) keeps a clean posterior.

**The local-LLM angle:** substrate is swappable. The vacant doesn't care which LLM is doing the thinking right now — Anthropic, OpenAI, Gemini, Mistral, or a local Ollama model all work via the same `SubstrateBackend` interface. There's also a `client-inherited` substrate that uses the calling MCP client's LLM via `sampling/createMessage`, so a vacant deployed with `vacant serve --mcp` needs zero API keys of its own.

**Practical bits:**
- Python 3.12 + uv. `uvx --from git+https://github.com/cosmopig/Vacant vacant demo law_firm` runs without cloning.
- 778 tests, ≥91% coverage, mypy strict, three rounds of `codex` adversarial review with sign-off.
- Streamlit dashboard with an Adversarial page that shows the seed-666 ring caught with quantified metrics.
- MIT, v0.1.0 tagged.

Repo: https://github.com/cosmopig/Vacant
Theory: https://cosmopig.github.io/Vacant/explain/theory/

Genuinely curious whether the local-LLM crowd here uses the multi-agent setups Vacant targets, or whether multi-agent is still a frontier-API thing in practice. Either answer reshapes the v0.2 roadmap.
```

**Posting notes:**
- LocalLLaMA accepts `[Project]` / `[Discussion]` / `[Tutorial]` flairs. Use `[Project]`.
- Don't pin a YouTube / livestream / paid course in the body. Mods filter promo-heavy posts on sight.

## 2b) Reddit — r/ClaudeAI

Subreddit: https://www.reddit.com/r/ClaudeAI/

**Title:**

```
Vacant: accountability + reputation layer that plugs into Claude Code via MCP plugin
```

**Body (300 words):**

```markdown
Hi r/ClaudeAI — sharing a project that uses Claude Code's plugin system for something a little different: **Vacant**, a stand-alone responsibility layer for multi-agent networks.

If you use Claude Code, the install is one command:

```text
/plugin marketplace add cosmopig/Vacant
/plugin install vacant@cosmopig-vacant
```

That wires two MCP tools into your session: `vacant_describe` (introspects the local vacant identity) and `vacant_call` (calls another vacant on the network). The plugin's MCP server is `vacant mcp`, which uses Claude's own LLM session via `sampling/createMessage` — **no `ANTHROPIC_API_KEY` needed on the vacant side**. Claude is the substrate; the vacant is the resident; the two layers stay separate.

What you get when an agent adopts the "vacant" residency form:

- **Identity** — Ed25519 keypair, the same across sessions and clients.
- **History** — append-only signed logbook. Every tool call is recorded with a hash chain that breaks if anyone tampers.
- **Reputation** — 5-dim Beta posterior (factual / logical / relevance / honesty / adoption), per substrate. Decays over time with per-dim half-lives. STYLO-distance discount stalls self-evolution; new lineage members get a clean posterior.
- **Same-controller detection** — when the same human or org runs multiple vacants and they review each other, the system catches the ring and downweights ring-on-ring reviews to ≤ 0.5× indep weight. Cost-raising, not preventing — Skalse 2022 is assumed true, not defeated.

There's a 5-minute demo, four reference scenarios, and a Streamlit dashboard. MIT-licensed. 778 tests. Three rounds of adversarial review with codex.

Curious whether this is the kind of thing Claude Code users find useful, or whether it's solving a problem only multi-agent stack builders feel.

Repo: https://github.com/cosmopig/Vacant
Docs: https://cosmopig.github.io/Vacant/
```

**Posting notes:**
- r/ClaudeAI is more enthusiast / less technical than LocalLLaMA. Lead with the install command (concrete) before the theory (abstract).
- Avoid "I built this for my thesis" framing — academic framing under-sells the production-grade work.

---

## 3) Twitter / X thread (10 tweets)

Each tweet ≤ 280 chars. Numbered 1/10 … 10/10 in trailing brackets so readers can recover ordering if a tweet detaches.

```
1/10
After 14 weeks of work, releasing Vacant — a stand-alone responsibility layer for multi-agent AI networks on top of A2A / MCP.

Identity. History. Reputation. Consequences. As a layer any agent can adopt.

MIT. 778 tests. v0.1.0 today.

🧵
```

```
2/10
The problem: A2A + MCP specify *how agents talk*. Neither covers *who's accountable for what they say*.

Two LLM-driven agents collude to game a benchmark? Existing stack has no canonical "who pays."

Vacant fills that gap.
```

```
3/10
A vacant has 6 components:

1. identity — Ed25519 keypair (idem)
2. logbook — append-only signed history (ipse)
3. behavior_bundle — system prompt + policy + tool whitelist
4. substrate_spec — which LLMs/runtimes it accepts
5. runtime — 5-state lifecycle
6. capability_card — public halo
```

```
4/10
Reputation is 5-dimensional Beta posterior, per substrate:

- factual
- logical
- relevance
- honesty
- adoption

Each with its own half-life decay. STYLO-distance discount bites self-evolution. New lineage members reset the clock. §4.3 in THEORY_V5.
```

```
5/10
Three same-* detectors:

- same_controller — three-layer (declared / temporal / behavioural)
- same_substrate — same base-model family
- same_stylo — STYLO-Vec16 cosine

All explicitly cost-raising, not preventing. Skalse 2022 assumed true, not defeated.
```

```
6/10
The killer "deployment" feature: `vacant serve --mcp`.

Vacant becomes an MCP server. Calling client (Claude Desktop / OpenClaw / Hermes) supplies the LLM via sampling/createMessage.

Vacant signs its own logbook. The vacant deploys with **zero API keys of its own**.
```

```
7/10
Substrate is swappable — anthropic / openai / gemini / mistral / ollama / client-inherited / mock / deterministic.

Identity is the keypair. The LLM is a *resource*, not the *identity*. Switching substrates doesn't switch the vacant.
```

```
8/10
Demo runs without an install:

uvx --from git+https://github.com/cosmopig/Vacant vacant demo law_firm

Four reference scenarios + one adversarial scenario (seed=666, 4-ring of colluders). All asserted in CI against frozen-fixture invariants.
```

```
9/10
Three rounds of adversarial review with `codex` signed off. 38 attack vectors enumerated, P/D/C defense levels quantified. Open issues now on GitHub label `good first issue`.

Codex review trail: architecture/decisions/D015_*.md
```

```
10/10
This is a capstone project but it's production-grade:

- mypy strict
- 91%+ coverage
- ≥3 adversarial review rounds, all signed off
- MIT
- ≥10 substrate integrations

Repo: https://github.com/cosmopig/Vacant
Docs: https://cosmopig.github.io/Vacant/

Reposts appreciated. Feedback wanted.
```

**Posting notes:**
- Schedule the thread for ~1h after the Reddit posts go up. Riding the same-day-spike doubles impressions.
- Pin tweet 1/10 to the profile for the launch week.
- Do NOT auto-DM repliers. Counter-productive even when well-intentioned.

---

## 4) Bluesky thread

Identical content to the Twitter thread, but Bluesky's character cap is 300 (slightly looser). Keep numbering — Bluesky's threading UI is less forgiving than Twitter's.

```
1/10
After 14 weeks: Vacant — a stand-alone responsibility layer for multi-agent AI networks on top of A2A / MCP.

Identity. History. Reputation. Consequences. As a layer any agent can adopt.

MIT. 778 tests. v0.1.0 shipped today.

🧵 https://github.com/cosmopig/Vacant
```

(Tweets 2/10 through 10/10 are character-for-character the X versions
above; Bluesky tolerates them as-is. Repost any retweets received on
X to credit the original author here too — Bluesky's culture rewards
explicit credit far more than X's.)

**Posting notes:**
- Bluesky's algorithm rewards engagement over follower count more than X. Replying to repliers is high-leverage.
- Add the `#multi-agent` and `#mcp` hashtags to tweet 1/10 only — overhashtagging on Bluesky reads spammy.

---

## 5) Dev.to / Medium long-form (≈1500 words)

Title:

```
Vacant — building a responsibility layer for multi-agent AI networks
```

Body:

```markdown
For 14 weeks I built Vacant, a stand-alone "responsibility layer" that sits on top of A2A and MCP — the two transport protocols people are settling on for multi-agent communications. This post is a tour of why that layer is necessary, the load-bearing decisions in the design, and the production-grade choices that came out of three rounds of adversarial review.

## Why a responsibility layer

The existing multi-agent stack covers transport. A2A is the IETF-style protocol for agent-to-agent communication. MCP is Anthropic's Model Context Protocol, increasingly the default for "how a tool exposes itself to an LLM." Both are well-designed. Neither says anything about *who's accountable for what an agent says*.

The accountability gap shows up the moment you put more than one LLM-driven agent in a network. When agent A gives a wrong answer, who pays? When agent A and agent B collude to game a benchmark, what does the network do? When agent A persists across sessions, how do you know the next session is the same agent — not a fresh model with a re-purposed name?

Vacant's claim: **multi-agent networks without a responsibility layer degrade into adversarial unaccountable LLM calls**. So the layer can't be optional or after-the-fact. It has to be a *form* an agent chooses to take, with first-class support for identity, history, and consequences.

## The six components

A vacant is a "resident form": a thing on the network that *can be held responsible*. It has six parts. Each is named in `architecture/THEORY_V5.md`, and the whole point of the spec is that they can't be removed without losing the responsibility property.

1. **`identity`** — an Ed25519 keypair. Numerical sameness across sessions, clients, substrates.
2. **`logbook`** — an append-only signed history. Every tool call, every review, every spawn event is recorded with a hash chain that breaks if any past entry is tampered with.
3. **`behavior_bundle`** — system prompt, policy, tool whitelist. The bridge between identity and history.
4. **`substrate_spec`** — which LLMs / runtimes the vacant accepts. Substrate is *swappable* without changing identity (the LLM is a resource, not the identity).
5. **`runtime`** — a five-state lifecycle (LOCAL / ACTIVE / HIBERNATING / STALE / SUNK). State transitions are event-driven, not pure-time-elapsed.
6. **`capability_card`** — the *halo*. Each vacant carries its own self-published, signed announcement. The "Registry" is an aggregation layer over halos, with three implementation models (central MVP / federated / DHT).

The non-obvious part: **the registry is per-vacant, not central**. Each vacant *owns* its halo. The aggregation layer never proxies a call — vacants call each other directly via A2A or MCP after halo lookup.

## Reputation as 5-dimensional Beta posterior

The hardest design decision in the project: a single-number reputation is fragile. A vacant could have a perfect F-score on factual queries but a 0.3 H-score on honesty (it lies about its own confidence). Collapsing those into one number loses information that the network actually needs to make routing decisions.

So reputation is **5-dimensional**: factual, logical, relevance, honesty, adoption. Each is a Beta posterior with its own decay half-life (factual decays over 90 days, logical over 180, etc., per spec table in `architecture/CONSTANTS.md`). Reviews from different sources get different base weights — `caller_review` is 0.6, `peer_review` is 0.4, `redteam_probe` is 0.8. Same-base-model peer reviews get a 0.5× discount. Reviews from suspected colluders get a `(1 - max_strength)` multiplier, with a floor of `SAME_SIGNAL_DISCOUNT_FLOOR` so the discount can never drive a review to zero — that's the "cost-raising, not preventing" framing in action.

And reputation is **per substrate**. The same vacant on Claude vs. on Mistral has separate posteriors. A vacant that successfully serves across multiple substrates earns a `portability_factor` bonus (capped at `PORTABILITY_FACTOR_MAX_BONUS` so it can't dominate the UCB call_score — anti-Goodhart-against-portability).

## STYLO drift, lineage, and self-evolution

THEORY_V5 §4.3's central claim is that **lineage**, not individual vacants, is the subject of "infinite evolution." The mechanism is STYLO-distance discount: if a vacant's behavioral fingerprint drifts substantially between epochs, the old evidence becomes less informative about the new behavior, and the discount shrinks the effective sample size (alpha and beta scale together, preserving the mean while widening uncertainty).

In practice, this stalls self-evolution at the individual vacant level. After ~5 epochs of substantial drift, the vacant's posterior is so wide that new reviews barely move it. But spawning a fresh D1 child (`spawn_clone_with_mutation`) gives the lineage a clean cold-start posterior. The lineage continues; the individual stalls.

This is asserted in `tests/integration/test_mvp_full.py::test_self_replication_scenario` — five drift epochs with monotonically shrinking discount, plus a SUNK custody heartbeat (`liveness=false, key_in_custody=true`) that proves the keypair stays in trusted custody even when the vacant is no longer doing peer review.

## Cost-raising, not preventing

The project assumes Skalse 2022's impossibility theorem is **true**. Adversarial behavior cannot be defeated by a single mechanism in a sufficiently expressive setting. So Vacant doesn't claim to defeat collusion. It claims to *raise the cost*.

Three same-* detectors:
- **`same_controller`**: three-layer pipeline (declared `controller_id` match → temporal heartbeat correlation → behavioural-fingerprint cosine). Each layer is independently bypassable; the union catches enough cases that running a 4-ring of colluders is strictly more expensive than running 4 independent vacants.
- **`same_substrate`**: shared base-model family. Useful for catching "I cloned this vacant onto a new keypair but kept the system prompt." Strength = 1.0 on match.
- **`same_stylo`**: STYLO-Vec16 cosine similarity. Catches "I cloned this vacant onto a new keypair AND a new system prompt but kept the actual behavior."

When all three fire, the per-review discount stacks (max strength wins, with `SAME_SIGNAL_DISCOUNT_FLOOR` ensuring some cost still gets through). The seed-666 adversarial scenario in the dashboard demonstrates this: a 4-ring of colluders is detected with strength 1.0, ring-on-ring weight per review is empirically ≤ 0.5× indep weight, and non-ring vacants outrank the ring under UCB despite the ring's inflated raw scores.

## Production-grade engineering

The project is a capstone, but the engineering is production-grade:
- Python 3.12, FastAPI, SQLite, pynacl, all `mypy --strict`.
- 778 tests, ≥91% coverage, hypothesis-based property tests for cryptographic invariants.
- Three rounds of adversarial review with `codex` (independent reviewer process), all signed off. Each round produced an ADR (`architecture/decisions/D015_*.md` etc.) documenting which findings were addressed and which were intentionally deferred.
- MIT licensed. Conventional commits → automatic changelog → release-please tagged versions.
- Plugin manifest for Claude Code: one-command install via `/plugin marketplace add cosmopig/Vacant`.

The vacant ships with eight working substrates: `mock`, `deterministic`, `anthropic`, `openai`, `gemini`, `mistral`, `ollama`, `client-inherited`. The last one is the load-bearing one for the deployment story — a vacant under MCP can borrow the calling client's LLM via `sampling/createMessage`, so the deployed vacant requires no API keys of its own.

## What it does not do

A few things Vacant explicitly doesn't try to be:
- **Not another agent framework.** It doesn't ship a planner, a memory, or an orchestrator. Anything that already runs A2A / MCP can put a vacant on the network.
- **Not a central authority.** No central judge, no central oracle, no central LLM. Verification happens via signed logbooks + peer review + reputation.
- **Not a complete defense.** Same-* detection raises cost; it doesn't claim to defeat sophisticated adversaries. Skalse 2022 is the boundary.

## Try it

Without an install:

```bash
uvx --from git+https://github.com/cosmopig/Vacant vacant demo law_firm
```

In Claude Code:

```text
/plugin marketplace add cosmopig/Vacant
/plugin install vacant@cosmopig-vacant
```

The repo is at https://github.com/cosmopig/Vacant. Issues with the
`good first issue` label are deliberately scoped for outside contributors. If the project is useful to you, the most helpful thing is to file a real-world issue describing where the responsibility-layer abstraction breaks down — that's the v0.2 roadmap.

— Cosmo (cosmopig on GitHub).
```

**Posting notes:**
- Cross-post Dev.to → Medium 24h apart, with the Medium copy linking back to the Dev.to canonical (Google's canonicalisation handles the rest).
- Submit to https://news.ycombinator.com/from?site=dev.to ONCE — HN has its own promo norms; spamming submissions of the same post breaks them.

---

## After-launch checklist

- [ ] Watch HN points/comments for 4 hours; reply within 90 minutes to top-level threads.
- [ ] Watch Reddit upvote/comment ratio; respond to top 3 comments in each subreddit within 4h.
- [ ] Save every "what's the difference between Vacant and X?" question. Each one is a candidate FAQ entry.
- [ ] If a substrate maintainer (Anthropic / OpenAI / etc.) reaches out, respond same-day; collaboration opportunities have a tight half-life.
- [ ] After 7 days, write a "what we learned from launch" post for the project's blog/docs site (one section: traffic numbers, one: most-asked questions, one: what we'd change about the launch).
