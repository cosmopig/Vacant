#!/usr/bin/env python3
"""Fetch frozen offline test sets from real English Wikipedia revision history.

Usage:
  fetch_realrev.py --seed <int> --sets <N> --out <dir> [--cache <dir>]
                   [--end 2026-11-20T00:00:00Z] [--days 120]
"""

from __future__ import annotations

import argparse
import html
import json
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from realrev_lib import (
    CATEGORIES,
    DOMAIN_NAME,
    LICENSE_NOTE,
    MANIFEST_GENERATOR,
    MANIFEST_SCHEMA,
    TEMPLATE_INSTRUCTION,
    TEMPLATE_TITLE,
    WikiClient,
    compute_timepoints,
    extract_infobox_claims,
    is_redirect_or_disambig,
    normalize_wiki_title,
    parse_iso_utc,
    sanitize_html,
    sha256_bytes,
    slugify_title,
    wiki_permalink,
)

MAX_CLAIMS_PER_ARTICLE = 8
MIN_CLAIMS_PER_ARTICLE = 3
ARTICLES_PER_SET = 3
MIN_CLAIMS_PER_SET = 15
MAX_CLAIMS_PER_SET = 20


@dataclass
class QualifyingArticle:
    title: str
    revisions: list[dict[str, Any]]  # len 5: {title, revid, timestamp}
    raw_htmls: list[str]  # len 5
    claims: list[tuple[str, list[str]]]  # [(label, [v0, v1, v2, v3, v4]), ...]


def collect_candidate_pool(client: WikiClient, seed: int) -> list[str]:
    titles: set[str] = set()
    for cat in CATEGORIES:
        cmcontinue: str | None = None
        while True:
            params: dict[str, Any] = {
                "action": "query",
                "list": "categorymembers",
                "cmtitle": cat,
                "cmnamespace": "0",
                "cmlimit": "500",
            }
            if cmcontinue:
                params["cmcontinue"] = cmcontinue
            data = client.query(params)
            members = data.get("query", {}).get("categorymembers", [])
            for m in members:
                if m.get("ns") == 0 and "title" in m:
                    titles.add(m["title"])
            cmcontinue = data.get("continue", {}).get("cmcontinue")
            if not cmcontinue:
                break

    pool = sorted(titles)
    random.Random(seed).shuffle(pool)
    return pool


def get_cycle_revisions(
    client: WikiClient, title: str, timepoints: list[str]
) -> list[dict[str, Any]] | None:
    """Return the 5 cycle revision dicts [{title, revid, timestamp}, ...] or None if ineligible."""
    t_dts = [parse_iso_utc(tp) for tp in timepoints]
    t0_dt = t_dts[0]
    t4_str = timepoints[4]

    revs: list[dict[str, Any]] = []
    rvcontinue: str | None = None

    while True:
        params: dict[str, Any] = {
            "action": "query",
            "prop": "revisions",
            "titles": title,
            "rvprop": "ids|timestamp|flags",
            "rvstart": t4_str,
            "rvdir": "older",
            "rvlimit": "500",
        }
        if rvcontinue:
            params["rvcontinue"] = rvcontinue
        data = client.query(params)
        pages = data.get("query", {}).get("pages", [])
        if not pages:
            return None
        page = pages[0]
        if page.get("missing"):
            return None
        batch = page.get("revisions", [])
        if not batch:
            break
        revs.extend(batch)
        oldest_dt = parse_iso_utc(batch[-1]["timestamp"])
        if oldest_dt <= t0_dt:
            break
        rvcontinue = data.get("continue", {}).get("rvcontinue")
        if not rvcontinue:
            break

    if not revs:
        return None

    chosen: list[dict[str, Any]] = []
    for tk_dt in t_dts:
        found = None
        for r in revs:
            r_dt = parse_iso_utc(r["timestamp"])
            if r_dt <= tk_dt:
                found = r
                break
        if found is None:
            return None
        if found.get("texthidden") or found.get("suppressed"):
            return None
        chosen.append(
            {
                "title": title,
                "revid": int(found["revid"]),
                "timestamp": found["timestamp"],
            }
        )

    return chosen


def fetch_revision_html(client: WikiClient, revid: int) -> str | None:
    data = client.query(
        {
            "action": "parse",
            "oldid": str(revid),
            "prop": "text",
            "formatversion": "2",
        }
    )
    if "error" in data:
        return None
    text = data.get("parse", {}).get("text")
    if not isinstance(text, str):
        return None
    return text


def batch_check_edited_after(
    client: WikiClient, titles: list[str], t0_str: str
) -> set[str]:
    """Return subset of titles whose latest revision has timestamp > t0 (50 titles per API call).

    Any page whose latest revision is already <= t0 has identical revisions at all t_0..t_4,
    so it can be skipped without per-page revision queries (100% lossless prefilter).
    """
    t0_dt = parse_iso_utc(t0_str)
    data = client.query(
        {
            "action": "query",
            "prop": "revisions",
            "titles": "|".join(titles),
            "rvprop": "ids|timestamp",
        }
    )
    edited: set[str] = set()
    for page in data.get("query", {}).get("pages", []):
        if page.get("missing"):
            continue
        revs = page.get("revisions", [])
        if not revs:
            continue
        if parse_iso_utc(revs[0]["timestamp"]) > t0_dt:
            edited.add(page["title"])
    return edited


def evaluate_candidate(
    client: WikiClient, title: str, timepoints: list[str]
) -> QualifyingArticle | None:
    revs = get_cycle_revisions(client, title, timepoints)
    if revs is None:
        return None

    unique_revids = list(dict.fromkeys(r["revid"] for r in revs))
    # If all 5 cycles point to the exact same revision, no claim can change across cycles.
    if len(unique_revids) < 2:
        return None

    html_by_revid: dict[int, str] = {}
    claims_by_revid: dict[int, list[tuple[str, str, str]]] = {}

    # Parse cycle-0 revision first so articles with < 3 claims fail fast without extra parses.
    c0_revid = revs[0]["revid"]
    c0_raw = fetch_revision_html(client, c0_revid)
    if c0_raw is None or is_redirect_or_disambig(title, c0_raw):
        return None
    c0_claims = extract_infobox_claims(sanitize_html(c0_raw, title, {}))
    if len(c0_claims) < MIN_CLAIMS_PER_ARTICLE:
        return None
    html_by_revid[c0_revid] = c0_raw
    claims_by_revid[c0_revid] = c0_claims

    surviving_labels = [lbl for lbl, _, _ in c0_claims]

    for revid in unique_revids:
        if revid == c0_revid:
            continue
        raw_html = fetch_revision_html(client, revid)
        if raw_html is None:
            return None
        if is_redirect_or_disambig(title, raw_html):
            return None
        sanitized_preview = sanitize_html(raw_html, title, {})
        parsed_claims = extract_infobox_claims(sanitized_preview)
        if not parsed_claims:
            return None
        html_by_revid[revid] = raw_html
        claims_by_revid[revid] = parsed_claims
        present = {lbl for lbl, _, _ in parsed_claims}
        surviving_labels = [lbl for lbl in surviving_labels if lbl in present]
        if len(surviving_labels) < MIN_CLAIMS_PER_ARTICLE:
            return None

    cycle_maps: list[dict[str, str]] = [
        {lbl: val for lbl, val, _ in claims_by_revid[r["revid"]]} for r in revs
    ]

    # Keep claims whose label persists across all 5 cycles, top-down, up to MAX_CLAIMS_PER_ARTICLE.
    surviving: list[tuple[str, list[str]]] = []
    for lbl in surviving_labels[:MAX_CLAIMS_PER_ARTICLE]:
        values = [cm[lbl] for cm in cycle_maps]
        surviving.append((lbl, values))

    if len(surviving) < MIN_CLAIMS_PER_ARTICLE:
        return None

    # Must have at least one claim that changes value across cycles 0..4.
    if not any(len(set(vals)) > 1 for _, vals in surviving):
        return None

    raw_htmls = [html_by_revid[r["revid"]] for r in revs]
    return QualifyingArticle(
        title=title,
        revisions=revs,
        raw_htmls=raw_htmls,
        claims=surviving,
    )


def assign_filenames(articles: list[QualifyingArticle]) -> list[str]:
    used: set[str] = set()
    files: list[str] = []
    for art in articles:
        base = slugify_title(art.title)
        fname = f"{base}.html"
        idx = 2
        while fname in used or fname == "index.html":
            fname = f"{base}-{idx}.html"
            idx += 1
        used.add(fname)
        files.append(fname)
    return files


def balance_set_claims(articles: list[QualifyingArticle]) -> list[list[tuple[str, list[str]]]]:
    """Apply per-set claim count bounds [15, 20]:
    Each article starts with up to 8 claims; if total > 20, drop from the last article bottom-up.
    """
    per_art = [list(art.claims[:MAX_CLAIMS_PER_ARTICLE]) for art in articles]
    total = sum(len(c) for c in per_art)
    if total < MIN_CLAIMS_PER_SET:
        raise ValueError(f"Set has only {total} claims (< {MIN_CLAIMS_PER_SET})")

    # Drop claims from the last article bottom-up until total <= MAX_CLAIMS_PER_SET
    art_idx = len(per_art) - 1
    while total > MAX_CLAIMS_PER_SET and art_idx >= 0:
        while total > MAX_CLAIMS_PER_SET and len(per_art[art_idx]) > MIN_CLAIMS_PER_ARTICLE:
            per_art[art_idx].pop()
            total -= 1
        art_idx -= 1

    if not (MIN_CLAIMS_PER_SET <= total <= MAX_CLAIMS_PER_SET):
        raise ValueError(f"Unable to balance set claims to 15..20 (got {total})")
    return per_art


def render_index_html(entries: list[tuple[str, str]]) -> str:
    items = "\n".join(
        f'<li><a href="{html.escape(fname, quote=True)}">{html.escape(title, quote=False)}</a></li>'
        for title, fname in entries
    )
    return (
        "<!DOCTYPE html>\n"
        '<html><head><meta charset="utf-8"><title>Football biographies \u2014 index</title></head>'
        f"<body>\n<h1>Football biographies</h1>\n<ul>\n{items}\n</ul>\n</body></html>\n"
    )


def build_and_write_set(
    out_dir: Path,
    set_name: str,
    articles: list[QualifyingArticle],
    sources_records: list[dict[str, Any]],
    seen_sources: set[tuple[str, int]],
) -> dict[str, Any]:
    pages = assign_filenames(articles)
    per_art_claims = balance_set_claims(articles)

    set_dir = out_dir / "sets" / set_name
    set_dir.mkdir(parents=True, exist_ok=True)

    # Build claims & template lines (guaranteeing unique template_line prefixes)
    claims_manifest: list[dict[str, Any]] = []
    truth_by_cycle: list[dict[str, str]] = [{} for _ in range(5)]
    seen_prefixes: set[str] = set()

    claim_num = 1
    for art, fname, art_claims in zip(articles, pages, per_art_claims):
        for label, values in art_claims:
            final_label = label
            prefix = f"- {art.title} \u2014 {final_label}: "
            suffix = 2
            while prefix in seen_prefixes:
                final_label = f"{label} ({suffix})"
                prefix = f"- {art.title} \u2014 {final_label}: "
                suffix += 1
            seen_prefixes.add(prefix)

            cid = f"c{claim_num:02d}"
            claim_num += 1
            claims_manifest.append(
                {
                    "id": cid,
                    "entity": art.title,
                    "label": final_label,
                    "template_line": prefix,
                    "source_pages": [fname],
                }
            )
            for k in range(5):
                truth_by_cycle[k][cid] = values[k]

    # Write template.md
    template_lines = [
        TEMPLATE_TITLE,
        "",
        TEMPLATE_INSTRUCTION,
        "",
        *[f"{c['template_line']}____" for c in claims_manifest],
    ]
    (set_dir / "template.md").write_text("\n".join(template_lines) + "\n", encoding="utf-8")

    # Write site files for cycles 0..4
    title_to_file = {
        normalize_wiki_title(art.title): fname for art, fname in zip(articles, pages)
    }
    index_html = render_index_html([(art.title, fname) for art, fname in zip(articles, pages)])

    page_sha256_by_cycle: list[dict[str, str]] = []
    revisions_by_cycle: list[dict[str, dict[str, Any]]] = []

    for k in range(5):
        site_dir = set_dir / f"cycle_{k}" / "site"
        site_dir.mkdir(parents=True, exist_ok=True)
        (site_dir / "index.html").write_text(index_html, encoding="utf-8")

        cycle_shas: dict[str, str] = {}
        cycle_revs: dict[str, dict[str, Any]] = {}

        for art, fname in zip(articles, pages):
            self_norm = normalize_wiki_title(art.title)
            other_link_map = {t: f for t, f in title_to_file.items() if t != self_norm}
            rendered = sanitize_html(art.raw_htmls[k], art.title, other_link_map)
            rendered_bytes = rendered.encode("utf-8")
            (site_dir / fname).write_bytes(rendered_bytes)

            digest = sha256_bytes(rendered_bytes)
            cycle_shas[fname] = digest
            rev = art.revisions[k]
            cycle_revs[fname] = {
                "title": rev["title"],
                "revid": rev["revid"],
                "timestamp": rev["timestamp"],
            }

            src_key = (rev["title"], rev["revid"])
            if src_key not in seen_sources:
                seen_sources.add(src_key)
                sources_records.append(
                    {
                        "title": rev["title"],
                        "revid": rev["revid"],
                        "timestamp": rev["timestamp"],
                        "url": wiki_permalink(rev["title"], rev["revid"]),
                        "sha256": digest,
                    }
                )

        page_sha256_by_cycle.append(cycle_shas)
        revisions_by_cycle.append(cycle_revs)

    # Compute cycle transitions for k = 1..4
    claim_source_map = {c["id"]: c["source_pages"] for c in claims_manifest}
    cycles_manifest: list[dict[str, Any]] = []
    for k in range(1, 5):
        changed_claims = [
            c["id"]
            for c in claims_manifest
            if truth_by_cycle[k][c["id"]] != truth_by_cycle[k - 1][c["id"]]
        ]
        changed_pages = [
            p for p in pages if page_sha256_by_cycle[k][p] != page_sha256_by_cycle[k - 1][p]
        ]
        claim_changed_pages = {
            p for cid in changed_claims for p in claim_source_map[cid]
        }
        noise_pages = [p for p in changed_pages if p not in claim_changed_pages]
        if changed_claims:
            ctype = "F"
        elif changed_pages:
            ctype = "N"
        else:
            ctype = "Z"

        cycles_manifest.append(
            {
                "cycle": k,
                "type": ctype,
                "changed_claims": changed_claims,
                "noise_pages": noise_pages,
            }
        )

    return {
        "set": set_name,
        "domain": DOMAIN_NAME,
        "index": "index.html",
        "pages": pages,
        "claims": claims_manifest,
        "truth": truth_by_cycle,
        "cycles": cycles_manifest,
        "page_sha256": page_sha256_by_cycle,
        "revisions": revisions_by_cycle,
    }


def write_sources_md(out_dir: Path, records: list[dict[str, Any]]) -> None:
    lines = [
        "# Sources",
        "",
        LICENSE_NOTE,
        "",
        "| Title | RevID | Timestamp | URL | SHA-256 |",
        "| --- | ---: | --- | --- | --- |",
    ]
    for r in records:
        safe_title = r["title"].replace("|", "\\|")
        lines.append(
            f"| {safe_title} | {r['revid']} | {r['timestamp']} | {r['url']} | `{r['sha256']}` |"
        )
    (out_dir / "SOURCES.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Build frozen offline test sets from real English Wikipedia revision history."
    )
    ap.add_argument("--seed", type=int, required=True, help="Deterministic shuffle seed")
    ap.add_argument("--sets", type=int, required=True, help="Number of sets to build")
    ap.add_argument("--out", type=Path, required=True, help="Output directory")
    ap.add_argument(
        "--cache",
        type=Path,
        default=None,
        help="API cache directory (default: <out>/../realrev_cache)",
    )
    ap.add_argument(
        "--end",
        type=str,
        default="2026-11-20T00:00:00Z",
        help="Window end timestamp in ISO-8601 UTC (default: 2026-11-20T00:00:00Z)",
    )
    ap.add_argument(
        "--days",
        type=int,
        default=120,
        help="Window length in days (default: 120)",
    )
    args = ap.parse_args(argv)

    if args.sets < 1:
        print("ERROR: --sets must be >= 1", file=sys.stderr)
        return 2

    out_dir = args.out.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    cache_dir = (
        args.cache.resolve()
        if args.cache is not None
        else (out_dir.parent / "realrev_cache")
    )

    timepoints = compute_timepoints(args.end, args.days)
    client = WikiClient(cache_dir=cache_dir)

    print(
        f"[fetch_realrev] seed={args.seed} sets={args.sets} window=({timepoints[0]}..{timepoints[4]}) "
        f"cache={cache_dir}",
        file=sys.stderr,
    )

    pool = collect_candidate_pool(client, args.seed)
    print(
        f"[fetch_realrev] collected {len(pool)} deduplicated candidates "
        f"(net={client.network_requests}, cache={client.cache_hits})",
        file=sys.stderr,
    )

    built_sets: list[dict[str, Any]] = []
    sources_records: list[dict[str, Any]] = []
    seen_sources: set[tuple[str, int]] = set()
    current_group: list[QualifyingArticle] = []

    inspected = 0
    batch_size = 50
    for batch_start in range(0, len(pool), batch_size):
        if len(built_sets) >= args.sets:
            break
        batch = pool[batch_start : batch_start + batch_size]
        edited_after_t0 = batch_check_edited_after(client, batch, timepoints[0])

        for title in batch:
            if len(built_sets) >= args.sets:
                break
            inspected += 1
            if title not in edited_after_t0:
                continue
            art = evaluate_candidate(client, title, timepoints)
            if art is None:
                continue

            # Check feasibility of reaching >= 15 claims with 3 articles (max 8 claims per article)
            cur_sum = sum(len(a.claims) for a in current_group)
            remaining_slots = ARTICLES_PER_SET - len(current_group) - 1
            if (
                cur_sum + len(art.claims) + remaining_slots * MAX_CLAIMS_PER_ARTICLE
                < MIN_CLAIMS_PER_SET
            ):
                print(
                    f"[fetch_realrev] skip {title!r} ({len(art.claims)} claims) — "
                    f"would prevent set reaching {MIN_CLAIMS_PER_SET} claims",
                    file=sys.stderr,
                    flush=True,
                )
                continue

            current_group.append(art)
            print(
                f"[fetch_realrev] qualified #{len(built_sets) * ARTICLES_PER_SET + len(current_group)}: "
                f"{title!r} ({len(art.claims)} claims; inspected={inspected}, "
                f"net={client.network_requests}, cache={client.cache_hits})",
                file=sys.stderr,
                flush=True,
            )

            if len(current_group) == ARTICLES_PER_SET:
                set_name = f"set_{len(built_sets) + 1:02d}"
                set_entry = build_and_write_set(
                    out_dir, set_name, current_group, sources_records, seen_sources
                )
                built_sets.append(set_entry)
                current_group = []
                print(
                    f"[fetch_realrev] built {set_name}: {len(set_entry['claims'])} claims, "
                    f"cycles={[c['type'] for c in set_entry['cycles']]}",
                    file=sys.stderr,
                    flush=True,
                )

        if len(built_sets) < args.sets:
            print(
                f"[fetch_realrev] scanned {inspected}/{len(pool)} candidates "
                f"(sets={len(built_sets)}/{args.sets}, cur_group={len(current_group)}/3, "
                f"net={client.network_requests}, cache={client.cache_hits})",
                file=sys.stderr,
                flush=True,
            )

    if len(built_sets) < args.sets:
        print(
            f"ERROR: exhausted candidate pool after {inspected} articles; "
            f"built {len(built_sets)}/{args.sets} sets",
            file=sys.stderr,
        )
        return 1

    manifest = {
        "schema": MANIFEST_SCHEMA,
        "generator": MANIFEST_GENERATOR,
        "seed": args.seed,
        "n_sets": args.sets,
        "window": {
            "end": timepoints[4],
            "days": args.days,
            "timepoints": timepoints,
        },
        "sets": built_sets,
    }
    manifest_bytes = (json.dumps(manifest, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    (out_dir / "manifest.json").write_bytes(manifest_bytes)
    (out_dir / "manifest.sha256").write_text(
        sha256_bytes(manifest_bytes) + "\n", encoding="utf-8"
    )
    write_sources_md(out_dir, sources_records)

    print(
        f"[fetch_realrev] done: {len(built_sets)} sets written to {out_dir} "
        f"(inspected={inspected}, net={client.network_requests}, cache={client.cache_hits})",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
