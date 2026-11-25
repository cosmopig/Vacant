# realrev_gen

Frozen, offline test set generator and validator built from real public revision history of English Wikipedia football biography articles, using Python 3.12 stdlib only.

## Programs

1. `fetch_realrev.py`:
   ```bash
   python3 fetch_realrev.py --seed <int> --sets <N> --out <dir> \
     [--cache <dir>] [--end 2026-11-20T00:00:00Z] [--days 120]
   ```
2. `check_realrev.py`:
   ```bash
   python3 check_realrev.py <dir>
   ```
   Exits non-zero on any schema, layout, checksum, infobox-verbatim, cycle-consistency, or template violation, and prints measured dataset shares.

## Network Etiquette & Caching

- Queries `https://en.wikipedia.org/w/api.php` only.
- Sends `User-Agent: d2-realrev-fetch/0.1 (offline research snapshot)` with no personal information.
- Rate-limited to at most 1 request per second (`min_interval = 1.05s`).
- Retries HTTP 429 and 5xx responses with exponential backoff (respecting `Retry-After`).
- Caches every API response as JSON under `<out>/../realrev_cache/` (or `--cache <dir>`) keyed by SHA-256 of canonicalized request parameters so reruns do not refetch.

## Fixed Selection Rules

All article, revision, and claim selections are applied mechanically with zero hand-picking:

1. **Candidate pool**: Collect namespace-0 (`cmnamespace=0`) members via `list=categorymembers` from:
   - `Category:EFL League Two players`
   - `Category:National League (English football) players`
   - `Category:Scottish Professional Football League players`
   Deduplicate titles, sort lexicographically by title, and shuffle deterministically with `random.Random(seed)`.
2. **Time window**: `W = (end − days, end]` with 5 evenly spaced timepoints:
   `t_k = end − (4 − k) · (days / 4)` for `k = 0..4` (`t_0 = end − days`, `t_4 = end`).
3. **Revision selection**: For each candidate in shuffled order, fetch revisions (`ids|timestamp|flags`) up to `t_4`. The page version at cycle `k` is the latest revision with `timestamp <= t_k`. Skip the article if any `t_k` has no revision, if any selected revision is deleted/suppressed, or if any selected revision renders as a redirect or disambiguation page. (Candidates whose five cycle revisions are all identical are skipped immediately since no claim can change across cycles.)
4. **HTML snapshot rendering**: Fetch each needed unique revision via `action=parse&oldid=<revid>&prop=text&formatversion=2`. Wrap in minimal `<html><head><title>…</title></head><body>…</body></html>`, strip `<script>` and `<style>` elements, keep tables intact, rewrite internal `/wiki/...` links targeting other articles in the same set to their local relative filenames, and leave all other links untouched.
5. **Infobox claim extraction**: Parse the first `<table>` with class containing `infobox` from cycle-0 HTML (ignoring hidden `display:none` elements and `<sup class="reference">` footnote markers, normalizing whitespace). Include every multi-cell row whose cells contain at least one digit and that is not a date/birth/age/height/years-only row:
   - For multi-cell career rows (`years | team | apps | (goals)`), the value is the statistic (e.g. `"45 (3)"`) and the label is the non-statistic cells joined with spaces plus `" apps (goals)"` (e.g. `"2023– Exampletown United apps (goals)"`).
   - Duplicate labels within an article are disambiguated top-down by appending `" (2)"`, `" (3)"`, etc.
   - Keep at most 8 claims per article, choosing rows top-down.
6. **Article qualification**: Drop any claim whose label disappears in any later cycle `1..4`. An article qualifies only if at least 3 claims remain across all 5 cycles and at least one of its kept claims takes a different value at some cycle `0..4`.
7. **Set assembly**: Each set consists of 3 qualifying articles taken consecutively in shuffled order (skipping an article only if accepting it would make reaching 15 total claims impossible for the current set), stopping once `N` sets are built. Each set has 15–20 claims total: if the 3 articles exceed 20 claims, claims are dropped from the last article bottom-up until 20 remain.

## Output Layout

```text
<out>/
  manifest.json        # schema: vacant.d2.manifest/1
  manifest.sha256      # sha256 hex of manifest.json bytes + newline
  SOURCES.md           # (title, revid, timestamp, url, sha256) + CC BY-SA 4.0 note
  sets/
    set_01/
      template.md      # verification report template with unique "- <Entity> — <label>: ____" lines
      cycle_0/site/    # index.html + <slug>.html files
      ...
      cycle_4/site/
```
