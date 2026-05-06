# Good first issues — drafts

This file is the staging area for issues we'd like to file under the
**`good first issue`** label once the repo is ready for outside
contributors. Each entry is a self-contained ticket: scope, file
range, expected LOC, and the skills a contributor would need.

The bar for "good first issue" here is:

- **Bounded scope.** A single contributor can finish in 2-4 hours.
- **No theory invariants.** Nothing that requires reading
  `architecture/THEORY_V5.md` cover-to-cover. (Theory-touching tickets
  go under `help wanted` instead.)
- **Clear acceptance.** A passing test or a visual diff, not "it
  feels better".
- **No coordination cost.** Doesn't depend on a half-merged branch.

When filing these, paste each block into a fresh GitHub issue, label
it `good first issue` + the matching component label, and link back
to this file in the issue body so the contributor can see the
surrounding context.

---

## 1. Live-API integration tests for OpenAI substrate

- **Component label:** `substrate`
- **Files:** `tests/integration/test_substrate_openai_live.py` (new) + `pyproject.toml` (add gating marker)
- **Estimated LOC:** ~80
- **Skills needed:** Python, pytest, `httpx`/`openai` SDK

Add a `@pytest.mark.live_openai` marker that runs **only** when
`OPENAI_API_KEY` is set. The test should:

1. Skip cleanly with `pytest.skip(...)` if the key is missing.
2. Run a single `vacant demo law_firm --substrate=openai` against the
   real API.
3. Assert the response envelope is well-formed (no schema violations)
   without asserting on the LLM's text output (text varies).
4. Time-bound the test to 60s.

Add the marker to `pyproject.toml` under `[tool.pytest.ini_options]
markers`. Document the env-var gating in `CONTRIBUTING.md` "Running
live-API tests" section.

**Acceptance:** the test passes locally with the key set, skips
without it, and CI does NOT run it (no key wired into GitHub Actions).

## 2. Live-API integration tests for Gemini, Mistral, Ollama

- **Component label:** `substrate`
- **Files:** three new files in `tests/integration/test_substrate_*_live.py`
- **Estimated LOC:** ~70 each (~210 total)
- **Skills needed:** same as #1 + `google-genai` / `mistralai` SDKs / Ollama HTTP

Once #1 lands, replicate the pattern for the other three substrates.
Ollama gating should check whether the local Ollama daemon is
reachable (`http://localhost:11434/api/tags`) rather than checking an
env var, since Ollama runs locally without an API key.

**Acceptance:** all three tests pass when their dependency is
available, skip cleanly when not.

## 3. Streamlit dashboard test

- **Component label:** `mvp`
- **Files:** `tests/integration/test_dashboard.py` (new)
- **Estimated LOC:** ~120
- **Skills needed:** Python, pytest, [`streamlit.testing.v1.AppTest`](https://docs.streamlit.io/develop/api-reference/app-testing/st.testing.v1.apptest)

The dashboard module currently has no tests — visual regressions slip
through. Add a smoke test using Streamlit's official `AppTest` API:

1. Spin up the dashboard in test mode.
2. Run each scenario page (`網路`, `血緣`, `情境`, `指標`, `對抗`).
3. Assert no exceptions surface and the expected element keys exist.
4. Mark `@pytest.mark.slow`.

This won't catch CSS regressions (Streamlit's headless test runner
doesn't render), but it catches the common breakage: a renamed metric
or moved scenario file that crashes the page on first paint.

**Acceptance:** the test runs in CI under the `slow` marker; one of
the existing scenarios is verified end-to-end through the dashboard.

## 4. Dark-mode toggle on the mkdocs site

- **Component label:** `docs`
- **Files:** `mkdocs.yml` (theme palette block)
- **Estimated LOC:** ~15
- **Skills needed:** mkdocs-material configuration

The site currently auto-switches based on `prefers-color-scheme`.
Many readers want a manual toggle that overrides the OS preference.
Add the manual `palette.toggle` to both palette entries (already
half-wired in `mkdocs.yml`), and add a small admonition in
`docs/index.md` mentioning the toggle is in the header.

**Acceptance:** open the deployed site, click the moon/sun icon in
the top bar, theme switches and persists per-tab.

## 5. Complete `.env.example` for all substrates

- **Component label:** `substrate`
- **Files:** `.env.example`
- **Estimated LOC:** ~20
- **Skills needed:** read the relevant SDK README

`.env.example` currently has placeholders for some substrates and
TODO comments for others (`NOUS_API_KEY`, `OPENCLAW_API_KEY`). Once
the upstream SDKs document their env-var conventions, update
`.env.example` with the canonical names and short comments linking to
the SDK doc URL.

**Acceptance:** every substrate listed in
`src/vacant/substrate/__init__.py` has a corresponding env-var entry
(commented out by default), with the exact upstream variable name.

## 6. ASCII diagram → Mermaid migration in README

- **Component label:** `docs`
- **Files:** `README.md`, `README.zh-TW.md`
- **Estimated LOC:** ~50 (diagrams stay roughly the same line count)
- **Skills needed:** Mermaid syntax + colour-blind-friendly palette

The "big picture" diagram is currently ASCII. GitHub renders Mermaid
inline now; converting gives:
- copy-paste friendly diagrams,
- a colour-blind-friendly default palette (avoid red+green pairs),
- searchable text inside the diagrams (ASCII isn't indexed).

Keep the ASCII version as a `<details>` collapsible fallback for
terminal-only viewers (man-page, plain `cat README.md`).

**Acceptance:** GitHub renders the Mermaid diagram on the README page
without errors; the fallback ASCII version is intact under
`<details>`.

## 7. Add `vacant demo --json-events` flag

- **Component label:** `cli`
- **Files:** `src/vacant/cli/commands.py`, `src/vacant/mvp/demo.py`,
  `tests/unit/test_cli.py`
- **Estimated LOC:** ~60
- **Skills needed:** Python, Typer, JSONL streaming

`vacant demo --tail` already streams demo-store events. Add a
sibling `--json-events` flag that emits JSON-Lines to stdout as the
scenario runs (one event per line). Useful for piping into `jq`,
`grep`, or external dashboards (Datadog / Sentry / ClickHouse) without
the formatted-text wrapper `--tail` produces.

**Acceptance:** `vacant demo law_firm --json-events | jq '.kind' |
sort -u` prints the set of event kinds seen during the run.

## 8. Hypothesis property test for the `same_controller` detector

- **Component label:** `reputation`
- **Files:** `tests/property/test_same_controller.py` (new)
- **Estimated LOC:** ~80
- **Skills needed:** [`hypothesis`](https://hypothesis.readthedocs.io/) strategies

The `same_controller(...)` detector is currently example-tested only.
Add property tests:

1. **Self-pair invariance:** for any vacant `a`,
   `same_controller(a, a, ...).strength == 0`.
2. **Symmetry:** swapping `a` and `b` produces the same `strength`
   (modulo float epsilon).
3. **Monotonicity in declared layer:** when `declared_same=True`,
   `strength >= SAME_CONTROLLER_DECLARED_STRENGTH`.
4. **Discount floor:** `discount_from_signals([sig])` is always
   `>= SAME_SIGNAL_DISCOUNT_FLOOR`, regardless of how many signals are
   stacked.

These properties are explicit in `architecture/THEORY_V5.md` §6 and
`architecture/decisions/D015_codex_review_2026_05_06.md`; the test
should cite each.

**Acceptance:** the property test runs under `pytest -m ""` and
hypothesis explores ≥1000 cases per property within 30s.

## 9. Add a "what changed" diff view to the dashboard

- **Component label:** `mvp` / `docs`
- **Files:** `src/vacant/mvp/dashboard.py`, possibly a tiny new helper
- **Estimated LOC:** ~80
- **Skills needed:** Python, Streamlit, `difflib`

When a contributor runs the same scenario twice with different seeds
or different substrate options, they currently have to inspect the
dashboard manually. Add a "compare two runs" page: pick run A and run
B from the demo-store, render a side-by-side diff of (1) reputation
distribution, (2) metric values, (3) event-count by kind. Use
`st.columns(2)` + `st.dataframe(highlight=...)` for the visualisation.

**Acceptance:** runs `law_firm` twice with different seeds, opens the
new diff page, sees per-vacant reputation differences highlighted
without re-running either scenario.

## 10. CITATION.cff round-trip test

- **Component label:** `meta`
- **Files:** `tests/unit/test_citation.py` (new)
- **Estimated LOC:** ~30
- **Skills needed:** Python, `cffconvert` (or just YAML parsing)

`CITATION.cff` is read by Zenodo / Software Heritage when the repo is
archived. A malformed file silently breaks academic citation. Add a
test that:

1. Parses `CITATION.cff` as YAML.
2. Asserts the required keys (`cff-version`, `title`, `authors`,
   `version`, `license`, `repository-code`) are present.
3. Asserts the `version` matches the project version in
   `pyproject.toml`.

**Acceptance:** `uv run pytest tests/unit/test_citation.py` passes
locally; intentionally breaking the YAML in a feature branch fails
the test as expected.
