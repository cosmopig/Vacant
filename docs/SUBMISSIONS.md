# SUBMISSIONS — awesome-list PR drafts

Internal reference. Not linked from the public site. Drafts the author
can paste verbatim (or trim) into upstream PRs once Vacant is ready
for outside readers.

The bar for awesome-lists is high — most accept items that meet **all**
of: live demo or working install, README in English, MIT/Apache/BSD
licence, ≥6 months of commits or a clear v0.x release tag, and an
active issue tracker. Vacant satisfies all five at v0.1.0; the entries
below highlight the load-bearing claim each list cares about.

## Submission order (suggested)

1. `awesome-mcp-servers` — easy yes; clear category fit.
2. `awesome-claude-code` — Claude-specific; mention the plugin manifest.
3. `awesome-multi-agent` / `awesome-llm-agent-frameworks` — broader; lead with the responsibility-layer framing rather than "another framework".

Submit one at a time, **week apart**, so each PR thread can be polished from the previous round's reviewer feedback.

---

## 1) awesome-mcp-servers

- Repo: https://github.com/punkpeye/awesome-mcp-servers
- Maintainer: `@punkpeye` (Frank Fiegel)
- File: `README.md`
- Section to add into: **`### 🤖 Agents`** subsection if Vacant is being submitted as an agent runtime that runs *over* MCP. If Vacant is presented as an MCP *server* (the `vacant serve --mcp` mode), then **`### 🤝 Multi-agent / Orchestration`** is the better fit. Pick one — do not double-list.

### Entry format (verbatim — match the surrounding bullets)

```markdown
- [cosmopig/Vacant](https://github.com/cosmopig/Vacant) 🐍 🏠 — A "responsibility-layer residency form" for AI agents on top of A2A / MCP. Gives any MCP-aware agent identity (Ed25519), an append-only signed history, 5-dimensional Beta reputation, and consequences. Ships as `vacant serve --mcp` with stdio + SSE transports; the calling client supplies the LLM via MCP `sampling/createMessage`, so the vacant deploys with no API key of its own.
```

The 🐍 = Python, 🏠 = self-hosted icons match the README's legend. Confirm the legend at PR time — `punkpeye` rotates the emoji set occasionally.

### PR title

```
Add Vacant — responsibility-layer residency form for MCP agents
```

### PR body

```markdown
Hi `@punkpeye` — submitting Vacant for inclusion.

**One-liner:** Vacant is a stand-alone "responsibility layer" that sits on top of MCP / A2A. An MCP-aware agent calls `vacant serve --mcp`, and the vacant carries identity (Ed25519 keypair), an append-only signed logbook, and a 5-dimensional Beta reputation that survives across sessions and clients.

**Why it fits:**
- Real MCP server (`mcp` SDK over stdio + SSE, not a re-implementation).
- The vacant uses `sampling/createMessage` to borrow the calling client's LLM, so the deployed vacant requires zero API keys of its own. This is the "嫁接到客戶端" (graft-onto-client) model the README explains in detail.
- Tested against `npx @modelcontextprotocol/inspector` (see `tests/integration/test_mcp_external_client.py`); demo screenshot in README.
- 778+ tests, ≥91% coverage, mypy strict, MIT licensed, v0.1.0 tagged.

**Standards:**
- ☑️ live demo (`uvx --from git+https://github.com/cosmopig/Vacant vacant demo law_firm`)
- ☑️ English README + repo description
- ☑️ MIT
- ☑️ active maintenance (changelog + release tags)
- ☑️ open issues + PR template

Thanks for keeping the list curated — happy to address any feedback.
```

---

## 2) awesome-claude-code

- Repo: https://github.com/hesreallyhim/awesome-claude-code (the most-starred general one) **and / or** https://github.com/eugeneyan/awesome-claude (alternative; less active, skip unless invited).
- Maintainer: `@hesreallyhim`
- File: `README.md`
- Section to add into: **`### Plugins`** if the list has a plugins subsection (it does at time of writing). Otherwise the closest existing category — `### Frameworks` or `### Tools`.

### Entry format

```markdown
- [Vacant](https://github.com/cosmopig/Vacant) — Adds an identity + reputation layer on top of Claude Code's MCP transport. Ships a `.claude-plugin/` manifest so `/plugin install cosmopig/Vacant` wires the demo + the `vacant serve --mcp` host into Claude Code in one command. Uses `sampling/createMessage` to borrow Claude's LLM — no `ANTHROPIC_API_KEY` needed on the vacant side.
```

### PR title

```
Add Vacant — identity + reputation plugin (one-command install)
```

### PR body

```markdown
Hi `@hesreallyhim` — submitting Vacant for the **Plugins** category.

**The Claude-Code-specific bits:**
- `.claude-plugin/plugin.json` manifest — `/plugin install cosmopig/Vacant` works out of the box.
- Three slash commands ship with the plugin: `/vacant-demo`, `/vacant-status`, `/vacant-call`.
- The vacant uses MCP `sampling/createMessage` to borrow Claude's LLM session, so no API key is required. Run `vacant serve --mcp`, point Claude Code at the SSE endpoint, done.

**The standards check:**
- MIT, English README + 繁體中文 README, v0.1.0 release with changelog.
- 778+ tests, ≥91% coverage, mypy strict, lint-clean.
- Active issue tracker + community files (CoC / CONTRIBUTING / SECURITY / good-first-issues).
- Public docs site at https://cosmopig.github.io/Vacant/ + live install via Zeabur.

**The novel piece** that might be worth highlighting in the entry copy: Vacant adds an *accountability* layer (signed logbook, 5-dim reputation, same-controller detection) without replacing any Claude-Code behaviour. It's purely additive — your existing prompts and tool whitelist keep working; the vacant just signs everything and surfaces a reputation score in the dashboard.

Happy to trim the entry to the list's tone — let me know if a single-clause summary fits better than the current two-sentence one.
```

---

## 3) awesome-multi-agent / awesome-llm-agent-frameworks

Two candidates; the better-curated one as of v0.1.0 is:

- Repo: https://github.com/kaushikb11/awesome-llm-agents (alternative: `https://github.com/Jenqyang/awesome-llm-agents` — confirm the most-starred at PR time).
- File: `README.md`
- Section: **`### Frameworks`** if the list has one; otherwise **`### Multi-agent`** or **`### Identity / Trust`** (Vacant fits last, but most lists don't have that section yet — start a category if invited).

The framing for these lists must lead with the **non-framework** angle: most multi-agent lists are framework-vs-framework comparisons (LangGraph, CrewAI, AutoGen, MetaGPT). Vacant is *not* a framework — it's a layer. Stress that.

### Entry format

```markdown
- [Vacant](https://github.com/cosmopig/Vacant) — A responsibility layer (not another framework) for multi-agent networks on A2A / MCP. Ed25519 identity, signed append-only history, 5-dimensional Beta reputation with STYLO-distance discount, same-controller / same-substrate / same-stylo detection (cost-raising, not preventing). Plugs into LangGraph / CrewAI / AutoGen agents via MCP without forcing them to migrate frameworks.
```

### PR title

```
Add Vacant — responsibility layer for multi-agent networks
```

### PR body

```markdown
Hi maintainer — Vacant is a stand-alone *responsibility layer* for multi-agent networks, not another agent framework. I'm submitting it because the list currently catalogues the "how do agents collaborate" frameworks but doesn't have any entries on the "who is accountable for what they say" problem. Vacant is one possible answer.

**The claim** (testable from the repo):
- A vacant is a residency form an agent chooses to take. It carries identity (Ed25519), history (signed logbook), and reputation (5-dim Beta posterior, decayed per spec, with STYLO-distance discount that bites self-evolution).
- Reputation defends against three known attacks at quantified cost: same-controller (≥ 0.5× weight ceiling on ring-on-ring reviews, asserted in `tests/integration/test_mvp_full.py::test_adversarial_seed_666_scenario`), same-substrate, same-stylo. Framing per CLAUDE.md: **cost-raising, not preventing** — the system doesn't claim to defeat the Skalse 2022 impossibility theorem.
- Ships with 4 reference scenarios + 1 adversarial scenario + 8 P7 metrics + a Streamlit dashboard.

**Why "not a framework":** Vacant doesn't ship a planner, a memory, or an orchestrator. Anything that already runs A2A / MCP can put a vacant on the network with `vacant serve`, then the existing planner/memory/orchestrator keeps its own design. The only coupling is the substrate handle (the vacant borrows the caller's LLM via MCP `sampling/createMessage`).

**Standards:**
- MIT, English + 繁體中文 README, v0.1.0 with changelog.
- 778+ tests, ≥91% coverage, mypy strict, three rounds of `codex` adversarial review with sign-off.
- Live demo: `uvx --from git+https://github.com/cosmopig/Vacant vacant demo adversarial`.

If a "Trust / Identity / Accountability" category doesn't exist yet, I'd be happy to draft a few neighbours (Olas, Mech Marketplace, others) so the section starts populated rather than as a single entry.
```

---

## Reviewer-feedback rules of thumb

- If a maintainer asks for shorter copy, drop the second sentence and keep the leading "responsibility-layer" claim.
- If a maintainer asks for benchmark numbers, link to `tests/integration/test_mvp_full.py` rather than pasting numbers (those drift; the test asserts the invariants).
- If a maintainer asks "is this a fork of X?", point to `architecture/THEORY_V5.md` §1-2 (no upstream — derived from Ricoeur's idem/ipse + Skalse 2022 + an original 5-dim Beta reputation model).
- If a maintainer asks for a graphical comparison, the README's "big picture" ASCII diagram is the canonical one — don't generate a new one for the PR.

## After-submission checklist

- [ ] Star the upstream awesome-list (signals good-faith participation).
- [ ] Watch the PR for 7 days; reply within 24h to maintainer questions.
- [ ] If accepted, add a "Featured in" badge to README only after the PR merges (not before — premature badges read as desperate).
- [ ] If rejected with feedback, file the feedback as `docs/SUBMISSIONS.md > Lessons` and try a different list rather than re-submitting the same content.
