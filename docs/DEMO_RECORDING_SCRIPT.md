# Demo recording script — 60-second README screencast

Storyboard for the README hero gif. The constraint is **60 seconds, no
voiceover, single GIF, ≤ 4 MB**. That budget forces the hard choices
below: which features get airtime, which slip to a follow-up.

## What this gif must accomplish

Three claims in 60 seconds:

1. **It runs.** A real `vacant demo` finishes in seconds with a deterministic mock substrate.
2. **It plugs into a client.** `vacant serve --mcp` connects to Claude Desktop without an API key on the vacant side.
3. **It detects collusion.** The dashboard's adversarial page shows the seed-666 ring caught with quantified weight downgrade.

If a fourth claim creeps in (lineage trees, STYLO discount, the
attestation chain), the gif goes over budget. Save those for follow-up
clips linked from `docs/DEMO_SCRIPT.md`.

## Storyboard (timed)

| t (s) | What's on screen | Caption (overlaid) |
|-------|------------------|--------------------|
| 0 – 2 | Black title card → fade in to terminal at zsh prompt. | "Vacant — responsibility layer for AI agents" |
| 2 – 8 | `uvx --from git+https://github.com/cosmopig/Vacant vacant demo law_firm` typed at full speed; output streams. | "1. Run the demo (no install, no API key)" |
| 8 – 16 | Demo finishes. `cat var/demo.db` summary appears (use `sqlite3 var/demo.db 'SELECT scenario, COUNT(*) FROM events GROUP BY scenario;'`). | "→ events written, signed, deterministic" |
| 16 – 22 | Open Streamlit dashboard, click `對抗 (Adversarial)` page. | "2. Adversarial page — seed=666" |
| 22 – 32 | Page shows the ring strength = 1.0 metric card + "ring weight per review ≤ 0.5× indep" green check + UCB ranking with non-ring vacants on top. | "ring detected · ring weight ≤ 0.5× indep · indep outranks ring" |
| 32 – 38 | Cut to a second terminal: `vacant serve --mcp --port 8443`. | "3. Plug into a client" |
| 38 – 48 | Claude Desktop window in the foreground. Type "Use the legal-qa vacant to draft an NDA clause." Cursor blinks. | "Claude Desktop calls the vacant" |
| 48 – 56 | Reply streams in. Bottom-right of the Claude window shows the vacant's signed envelope + reputation card. | "no `ANTHROPIC_API_KEY` on the vacant — sampling/createMessage" |
| 56 – 60 | Fade to title card with URL. | "github.com/cosmopig/Vacant — MIT, Theory V5, 778 tests" |

The single hardest cut to land cleanly is **22–32s**: the dashboard
needs to show *three* signals (strength card, weight ratio, UCB
ranking) without a scroll. Pre-resize the browser window to ~1280x720
and pin the dashboard zoom to 90% so all three sit above the fold.

## Tooling

Recommended stack — all free + open-source:

| Stage | Tool | Why |
|-------|------|-----|
| Terminal capture | [`asciinema`](https://asciinema.org) | Vector-perfect terminal session; copy/pasteable from the published page if a viewer wants the commands. |
| Asciinema → GIF | [`agg`](https://github.com/asciinema/agg) | First-party converter; respects the original timing. |
| GUI capture (dashboard + Claude Desktop) | [`peek`](https://github.com/phw/peek) (Linux), [`Gifox`](https://gifox.app/) (macOS), or [`ScreenToGif`](https://www.screentogif.com/) (Windows) | All three produce small palettised GIFs out of the box. |
| Splice + retime | [`gifski`](https://gif.ski/) | Best palette + framerate control among GIF encoders. Use `--fps 12 --quality 80` for a balance between size and smoothness. |
| Caption overlay | [`ffmpeg`](https://ffmpeg.org/) `drawtext` filter | Avoid editing each frame manually; one ffmpeg pass adds the caption track from a `subs.txt` file. |
| Final size pass | [`gifsicle`](https://www.lcdf.org/gifsicle/) `-O3 --lossy=80` | Last-mile compression. Aim for ≤ 4 MB so README renders fast on cellular. |

For viewers who can't load the gif, also publish the equivalent
asciinema cast (terminal portion only, no Claude Desktop) at
`https://asciinema.org/a/<id>` and link it under the gif. Asciinema
casts are tiny (~50 KB), text-searchable, and accessible.

## Recording-day checklist

Pre-flight:

- [ ] Fresh checkout of `cosmopig/Vacant` at the latest release tag.
- [ ] Empty `~/.vacant/`, empty `var/demo.db`, no `ANTHROPIC_API_KEY` exported (the gif's whole pitch is no-key).
- [ ] Claude Desktop logged in; MCP transport configured to point at `localhost:8443`.
- [ ] Terminal at 110×30, 14pt monospace, dark theme. No `$PROMPT` modifications that leak the host name.
- [ ] Dashboard pre-warmed — run each scenario once before recording so the cache is hot and the page paints fast.
- [ ] Resolution pinned to 1280×720 across both terminal and browser captures so the cuts align.

Take care of:

- [ ] Hide secrets. `~/.zsh_history` autocomplete can leak. Run with `HISTFILE=/dev/null zsh`.
- [ ] Mouse cursor — bright theme cursors disappear in dark recordings; force the OS cursor to a high-contrast variant.
- [ ] Text legibility on cellular: caption font ≥ 24px in the GIF; never put load-bearing detail in 12px terminal text without a caption.

Post-flight:

- [ ] Re-watch at 0.5× speed once. If you can't read a caption while paused, re-record that segment.
- [ ] Commit the final gif to `assets/demo.gif`. README placeholder block in this PR auto-resolves once the file lands at that path.
- [ ] Add the asciinema cast URL to `docs/DEMO_SCRIPT.md` "Companion materials".

## What we deliberately don't put in the gif

- **Lineage tree visualisation.** Beautiful but slow to read at gif speed; goes in a follow-up clip.
- **STYLO discount math.** Five-line formula won't fit; the docs site explains it.
- **Code review scenario.** Visually similar to law_firm; redundant for the hero.
- **`vacant demo --tail` streaming view.** Cool but adds 10s without a new claim.

If a follow-up demo is recorded later, the natural sequence is
60-second hero (this script) → 3-minute deep-dive (`docs/DEMO_SCRIPT.md`)
→ live-defense walkthrough (linked from the capstone defense slides
when those go public).
