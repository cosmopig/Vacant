#!/usr/bin/env python3
"""Deterministic generator of synthetic multi-format web source sets.

Usage:
    python3 gen_heldout.py --seed <int> --sets <N> --out <dir>
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import random
import re
import sys
import textwrap
from dataclasses import dataclass
from pathlib import Path

from domains import AttrSpec, DOMAINS, DomainSpec, PageSpec

SCHEMA_VERSION = "vacant.d2.manifest/1"
GENERATOR_NAME = "heldout-v1"
CYCLE_TYPES_MULTISET = ["F", "F", "N", "Z"]

VALUE_TOKEN_RE = re.compile(
    r"(?<![A-Za-z0-9.])v\d+\.\d+\.\d+(?![A-Za-z0-9.])"
    r"|(?<![A-Za-z0-9.,])\d{1,3}(?:,\d{3})+(?:\.\d+)?(?![A-Za-z0-9.,])"
    r"|(?<![A-Za-z0-9.,])\d+(?:\.\d+)?(?![A-Za-z0-9.,])"
)


def extract_single_token(value: str) -> str:
    """Return the unique number or version token in value, or raise ValueError."""
    matches = list(VALUE_TOKEN_RE.finditer(value))
    if len(matches) != 1:
        raise ValueError(f"Expected 1 numeric/version token in {value!r}, found {len(matches)}")
    m = matches[0]
    remainder = value[: m.start()] + value[m.end() :]
    if re.search(r"\d", remainder):
        raise ValueError(f"Unexpected stray digits in {value!r}")
    return m.group(0)


def token_key(token: str) -> tuple:
    """Canonical comparable key for a numeric or version token."""
    if token.startswith("v"):
        return ("v",) + tuple(int(p) for p in token[1:].split("."))
    num = float(token.replace(",", ""))
    return ("n", round(num, 6))


def format_attr_value(attr: AttrSpec, raw_val: object) -> str:
    if attr.kind == "int_unit":
        n = int(raw_val)  # type: ignore[arg-type]
        num_str = f"{n:,}" if n >= 1000 else str(n)
        return f"{num_str} {attr.unit}" if attr.unit else num_str
    if attr.kind == "decimal_unit":
        f = float(raw_val)  # type: ignore[arg-type]
        return f"{f:.1f} {attr.unit}" if attr.unit else f"{f:.1f}"
    if attr.kind == "currency_cents":
        f = float(raw_val)  # type: ignore[arg-type]
        return f"${f:,.2f}"
    if attr.kind == "currency_whole":
        n = int(raw_val)  # type: ignore[arg-type]
        return f"${n:,}"
    if attr.kind == "percent":
        n = int(raw_val)  # type: ignore[arg-type]
        return f"{n}%"
    if attr.kind == "version":
        major, minor, patch = raw_val  # type: ignore[misc]
        return f"v{major}.{minor}.{patch}"
    raise ValueError(f"Unknown attr kind: {attr.kind}")


def sample_raw_value(attr: AttrSpec, rng: random.Random) -> object:
    if attr.kind == "int_unit":
        lo, hi = int(attr.lo), int(attr.hi)
        if hi >= 5000:
            step = 50
            choices = list(range((lo // step) * step + step, hi + 1, step))
            return rng.choice(choices) if choices else rng.randint(lo, hi)
        if hi >= 1000:
            step = 10
            choices = list(range((lo // step) * step + step, hi + 1, step))
            return rng.choice(choices) if choices else rng.randint(lo, hi)
        return rng.randint(lo, hi)
    if attr.kind == "decimal_unit":
        lo10 = int(round(attr.lo * 10))
        hi10 = int(round(attr.hi * 10))
        return rng.randint(lo10, hi10) / 10.0
    if attr.kind == "currency_cents":
        lo_q = int(round(attr.lo * 4))
        hi_q = int(round(attr.hi * 4))
        return rng.randint(lo_q, hi_q) / 4.0
    if attr.kind == "currency_whole":
        lo, hi = int(attr.lo), int(attr.hi)
        step = 50
        choices = list(range(((lo + step - 1) // step) * step, hi + 1, step))
        return rng.choice(choices) if choices else rng.randint(lo, hi)
    if attr.kind == "percent":
        return rng.randint(int(attr.lo), int(attr.hi))
    if attr.kind == "version":
        major = rng.randint(int(attr.lo), int(attr.hi))
        minor = rng.randint(1, 18)
        patch = rng.randint(0, 9)
        return (major, minor, patch)
    raise ValueError(f"Unknown attr kind: {attr.kind}")


def sample_updated_value(attr: AttrSpec, old_str: str, old_raw: object, rng: random.Random) -> str:
    """Sample a realistic updated value strictly differing in its numeric/version token."""
    old_tok = token_key(extract_single_token(old_str))
    for _ in range(64):
        if attr.kind == "version":
            major, minor, patch = old_raw  # type: ignore[misc]
            bump = rng.choice(["patch", "patch", "minor"])
            if bump == "patch":
                new_raw: object = (major, minor, patch + rng.randint(1, 3))
            else:
                new_raw = (major, minor + 1, rng.randint(0, 2))
        else:
            new_raw = sample_raw_value(attr, rng)
        new_str = format_attr_value(attr, new_raw)
        if new_str != old_str and token_key(extract_single_token(new_str)) != old_tok:
            return new_str
    raise RuntimeError(f"Could not sample distinct updated value for {attr.label}")


def make_distractor_ctx(org: str, region: str, town: str, rng: random.Random) -> dict[str, str]:
    """Generate realistic distractor values for narrative prose slots."""
    return {
        "org": org,
        "region": region,
        "town": town,
        "d_year": str(rng.randint(1982, 2023)),
        "d_count": f"{rng.randint(18, 420):,}",
        "d_small": str(rng.randint(3, 12)),
        "d_pct": f"{rng.randint(12, 78)}%",
        "d_fee": f"${rng.randint(4, 24)}.{rng.choice(['00', '50'])}",
        "d_age": str(rng.randint(6, 14)),
        "d_mins": str(rng.choice([30, 45, 60, 75, 90])),
    }


@dataclass
class ClaimDef:
    cid: str
    entity: str
    attr: AttrSpec
    template_line: str
    v0: str
    v1: str
    source_pages: list[str]


@dataclass
class ClaimSlot:
    cid: str
    sentence_template: str  # contains "{value}"
    ctx: dict[str, str]
    companion: str


@dataclass
class PageModel:
    filename: str
    fmt: str  # ".html" | ".md" | ".txt"
    title: str
    description: str
    intro: str
    section_titles: list[str]
    noise_variants: list[list[str]]  # list of unclaimed paragraphs, each having 4 rendered variants
    claim_slots: list[ClaimSlot]
    bullets: list[str]  # empty or 2-3 prose bullets (at most one small list per page)


def protect_wrap(text: str, protected_spans: list[str], width: int = 82) -> str:
    """Wrap plain text to width without breaking inside any protected claim value string."""
    sentinel = "\u00a0"  # temporary non-breaking placeholder
    work = text
    # Sort longest first to avoid partial overlap issues
    for span in sorted(set(protected_spans), key=len, reverse=True):
        if " " in span and span in work:
            work = work.replace(span, span.replace(" ", sentinel))
    wrapped = textwrap.fill(
        work,
        width=width,
        break_long_words=False,
        break_on_hyphens=False,
    )
    return wrapped.replace(sentinel, " ")


def render_content_page(
    page: PageModel,
    org_name: str,
    index_filename: str,
    truth: dict[str, str],
    noise_indices: list[int],
) -> str:
    """Render a content page deterministically in .html, .md, or .txt format."""
    # Assemble narrative paragraphs grouped into sections
    active_noise = [page.noise_variants[i][noise_indices[i]] for i in range(len(page.noise_variants))]

    # Render claim paragraphs (each combining the claim sentence + a contextual narrative sentence)
    claim_paragraphs: list[tuple[str, str]] = []  # (paragraph_text, claim_value)
    for slot in page.claim_slots:
        val = truth[slot.cid]
        c_sent = slot.sentence_template.format(value=val, **slot.ctx)
        para = f"{c_sent} {slot.companion}"
        claim_paragraphs.append((para, val))

    # Interleave unclaimed prose paragraphs and claim paragraphs across 2-3 sections
    # Section 0: intro + first noise block + first half of claims
    # Section 1: second noise block + second half of claims (+ optional small list)
    # Section 2: third noise block (if any)
    mid = (len(claim_paragraphs) + 1) // 2
    sec0_paras = [page.intro]
    sec0_vals: list[str] = []
    if len(active_noise) > 0:
        sec0_paras.append(active_noise[0])
    for p, v in claim_paragraphs[:mid]:
        sec0_paras.append(p)
        sec0_vals.append(v)

    sec1_paras: list[str] = []
    sec1_vals: list[str] = []
    if len(active_noise) > 1:
        sec1_paras.append(active_noise[1])
    for p, v in claim_paragraphs[mid:]:
        sec1_paras.append(p)
        sec1_vals.append(v)

    sec2_paras: list[str] = []
    if len(active_noise) > 2:
        sec2_paras.extend(active_noise[2:])

    sections: list[tuple[str, list[str], list[str], list[str]]] = [
        (page.section_titles[0], sec0_paras, sec0_vals, []),
        (page.section_titles[1], sec1_paras, sec1_vals, page.bullets),
    ]
    if sec2_paras:
        sections.append((page.section_titles[2], sec2_paras, [], []))

    if page.fmt == ".html":
        lines = [
            "<!DOCTYPE html>",
            '<html lang="en">',
            "<head>",
            '  <meta charset="utf-8">',
            f"  <title>{html.escape(page.title)} — {html.escape(org_name)}</title>",
            "  <style>",
            "    body { font-family: Georgia, serif; max-width: 760px; margin: 2rem auto; padding: 0 1rem; line-height: 1.6; color: #222; }",
            "    header, footer { border-bottom: 1px solid #ccc; padding-bottom: 0.5rem; margin-bottom: 1.5rem; }",
            "    footer { border-bottom: none; border-top: 1px solid #ccc; margin-top: 2rem; padding-top: 0.75rem; font-size: 0.9rem; color: #555; }",
            "    h1 { margin-bottom: 0.25rem; }",
            "    h2 { margin-top: 1.75rem; color: #333; }",
            "  </style>",
            "</head>",
            "<body>",
            "  <header>",
            f"    <p><strong>{html.escape(org_name)}</strong> &middot; <a href=\"{html.escape(index_filename)}\">Directory Index</a></p>",
            f"    <h1>{html.escape(page.title)}</h1>",
            "  </header>",
            "  <main>",
        ]
        for heading, paras, _vals, bullets in sections:
            lines.append("    <section>")
            lines.append(f"      <h2>{html.escape(heading)}</h2>")
            for p in paras:
                lines.append(f"      <p>{html.escape(p)}</p>")
            if bullets:
                lines.append("      <ul>")
                for b in bullets:
                    lines.append(f"        <li>{html.escape(b)}</li>")
                lines.append("      </ul>")
            lines.append("    </section>")
        lines.extend(
            [
                "  </main>",
                "  <footer>",
                f"    <p>Published by {html.escape(org_name)}. Return to <a href=\"{html.escape(index_filename)}\">{html.escape(index_filename)}</a>.</p>",
                "  </footer>",
                "</body>",
                "</html>",
                "",
            ]
        )
        return "\n".join(lines)

    if page.fmt == ".md":
        lines = [
            f"# {page.title}",
            "",
            f"*{org_name}* — [Back to directory]({index_filename})",
            "",
        ]
        for heading, paras, _vals, bullets in sections:
            lines.append(f"## {heading}")
            lines.append("")
            for p in paras:
                lines.append(p)
                lines.append("")
            if bullets:
                for b in bullets:
                    lines.append(f"- {b}")
                lines.append("")
        lines.append("---")
        lines.append(f"Source directory: [{index_filename}]({index_filename})")
        lines.append("")
        return "\n".join(lines)

    if page.fmt == ".txt":
        title_line = f"{page.title.upper()} ({org_name})"
        lines = [
            title_line,
            "=" * len(title_line),
            f"Directory index: {index_filename}",
            "",
        ]
        for heading, paras, vals, bullets in sections:
            lines.append(heading)
            lines.append("-" * len(heading))
            lines.append("")
            for p in paras:
                lines.append(protect_wrap(p, vals, width=82))
                lines.append("")
            if bullets:
                for b in bullets:
                    wrapped_b = textwrap.fill(
                        b,
                        width=80,
                        initial_indent="* ",
                        subsequent_indent="  ",
                        break_long_words=False,
                        break_on_hyphens=False,
                    )
                    lines.append(wrapped_b)
                lines.append("")
        lines.append(f"-- End of document ({org_name}; see {index_filename}) --")
        lines.append("")
        return "\n".join(lines)

    raise ValueError(f"Unsupported format: {page.fmt}")


def render_index_page(
    index_filename: str,
    index_fmt: str,
    org_name: str,
    intro: str,
    pages: list[PageModel],
) -> str:
    """Render the site index listing every content page with description and relative link."""
    if index_fmt == ".html":
        lines = [
            "<!DOCTYPE html>",
            '<html lang="en">',
            "<head>",
            '  <meta charset="utf-8">',
            f"  <title>{html.escape(org_name)} — Site Directory</title>",
            "  <style>",
            "    body { font-family: Georgia, serif; max-width: 760px; margin: 2rem auto; padding: 0 1rem; line-height: 1.6; color: #222; }",
            "    ul { padding-left: 1.25rem; }",
            "    li { margin-bottom: 0.6rem; }",
            "  </style>",
            "</head>",
            "<body>",
            f"  <h1>{html.escape(org_name)}</h1>",
            f"  <p>{html.escape(intro)}</p>",
            "  <h2>Published Pages</h2>",
            "  <ul>",
        ]
        for p in pages:
            lines.append(
                f'    <li><a href="{html.escape(p.filename)}">{html.escape(p.title)}</a> — {html.escape(p.description)}</li>'
            )
        lines.extend(
            [
                "  </ul>",
                "</body>",
                "</html>",
                "",
            ]
        )
        return "\n".join(lines)

    if index_fmt == ".md":
        lines = [
            f"# {org_name}",
            "",
            intro,
            "",
            "## Published Pages",
            "",
        ]
        for p in pages:
            lines.append(f"- [{p.title}]({p.filename}) — {p.description}")
        lines.append("")
        return "\n".join(lines)

    if index_fmt == ".txt":
        header = f"{org_name.upper()} — SITE DIRECTORY"
        lines = [
            header,
            "=" * len(header),
            "",
            textwrap.fill(intro, width=82),
            "",
            "Published Pages",
            "---------------",
            "",
        ]
        for p in pages:
            lines.append(f"* {p.title} ({p.filename}) — {p.description}")
        lines.append("")
        return "\n".join(lines)

    raise ValueError(f"Unsupported index format: {index_fmt}")


def render_template_md(org_name: str, entities: list[str], claims: list[ClaimDef]) -> str:
    """Render template.md with title, instruction line, optional entity headings, and 20 blanks."""
    lines = [
        f"# {org_name} — Fact Report",
        "",
        "Fill in each blank with the exact current value reported on the source pages, including any unit or currency symbol.",
        "",
    ]
    by_entity: dict[str, list[ClaimDef]] = {e: [] for e in entities}
    for c in claims:
        by_entity[c.entity].append(c)

    for ent in entities:
        lines.append(f"## {ent}")
        lines.append("")
        for c in by_entity[ent]:
            lines.append(f"{c.template_line}____")
        lines.append("")
    return "\n".join(lines)


def assign_formats(n_pages: int, rng: random.Random) -> tuple[str, str, list[str]]:
    """Choose index filename/format and content page formats, guaranteeing >= 2 formats."""
    all_fmts = [".html", ".md", ".txt"]
    # Usually use all 3 formats across content pages; sometimes 2 formats for variety.
    use_three = rng.random() < 0.75
    if use_three:
        chosen_pool = list(all_fmts)
        rng.shuffle(chosen_pool)
        # Ensure all 3 formats appear at least once among the 5-7 content pages
        page_fmts = list(chosen_pool)
        while len(page_fmts) < n_pages:
            page_fmts.append(rng.choice(chosen_pool))
    else:
        chosen_pool = rng.sample(all_fmts, 2)
        page_fmts = list(chosen_pool)
        while len(page_fmts) < n_pages:
            page_fmts.append(rng.choice(chosen_pool))
    rng.shuffle(page_fmts)

    index_choices = [
        ("index.html", ".html"),
        ("index.md", ".md"),
        ("site-index.txt", ".txt"),
    ]
    # Prefer index.html or index.md most often, occasionally site-index.txt
    weights = [0.45, 0.40, 0.15]
    idx_file, idx_fmt = rng.choices(index_choices, weights=weights, k=1)[0]
    return idx_file, idx_fmt, page_fmts


def choose_section_titles(page_spec: PageSpec, rng: random.Random) -> list[str]:
    bank = {
        "overview": [
            ["Executive Notes", "Key Figures Across the Network", "Regional Outlook"],
            ["Annual Highlights", "Operational Summary", "Looking Ahead"],
            ["Network Snapshot", "Current Highlights", "Community Context"],
        ],
        "entities": [
            ["Field Profiles", "Current Operational Notes", "Stewardship Details"],
            ["Directory Notes", "Measured Figures", "Additional Background"],
            ["Site Overview", "Active Metrics", "Maintenance & Care"],
        ],
        "operations": [
            ["Operational Review", "Reported Figures", "Administrative Notes"],
            ["Current Policies", "Audit & Field Numbers", "Seasonal Planning"],
            ["Service Details", "Measured Performance", "Ongoing Upkeep"],
        ],
        "community": [
            ["Community Notes", "Program Figures", "Neighborhood Updates"],
            ["Public Guidance", "Current Participation", "Local Partnerships"],
            ["Everyday Guide", "Reported Activity", "Seasonal Reminders"],
        ],
        "faq": [
            ["Common Questions", "Reference Figures", "Further Guidance"],
            ["Visitor Answers", "Current Details", "Helpful Reminders"],
            ["Frequently Asked", "Verified Figures", "Practical Notes"],
        ],
    }
    return list(rng.choice(bank[page_spec.role]))


def build_set(
    set_id: str,
    domain: DomainSpec,
    set_rng: random.Random,
    set_dir: Path,
) -> dict:
    """Generate one complete synthetic set across cycles 0..4 and write it to disk."""
    org_name, region, town = set_rng.choice(domain.org_choices)
    # 1. Pick 4-6 entities
    n_entities = set_rng.choice([4, 5, 6])
    entities = set_rng.sample(list(domain.entities), n_entities)

    # Distribute 20 claims across n_entities
    if n_entities == 4:
        counts = [5, 5, 5, 5]
    elif n_entities == 5:
        counts = [4, 4, 4, 4, 4]
    else:
        counts = [4, 4, 3, 3, 3, 3]
        set_rng.shuffle(counts)

    # 2. Pick 5-7 content pages (always include the overview page)
    n_pages = set_rng.choice([5, 6, 7])
    overview_pages = [p for p in domain.pages if p.role == "overview"]
    other_pages = [p for p in domain.pages if p.role != "overview"]
    selected_specs = [overview_pages[0]] + set_rng.sample(other_pages, n_pages - 1)
    # Put overview first, rest in a shuffled order
    tail = selected_specs[1:]
    set_rng.shuffle(tail)
    selected_specs = [selected_specs[0]] + tail

    index_filename, index_fmt, page_fmts = assign_formats(n_pages, set_rng)
    page_filenames = [f"{spec.slug}{fmt}" for spec, fmt in zip(selected_specs, page_fmts)]
    assert index_filename not in page_filenames

    # 3. Create 20 unique claims grouped by entity
    claims: list[ClaimDef] = []
    cid_num = 1
    for ent, k in zip(entities, counts):
        chosen_attrs = set_rng.sample(list(domain.attributes), k)
        for attr in chosen_attrs:
            cid = f"c{cid_num:02d}"
            cid_num += 1
            raw0 = sample_raw_value(attr, set_rng)
            v0 = format_attr_value(attr, raw0)
            v1 = sample_updated_value(attr, v0, raw0, set_rng)
            # Validate both values strictly
            extract_single_token(v0)
            extract_single_token(v1)
            assert html.escape(v0) == v0 and html.escape(v1) == v1
            t_line = f"- {ent} \u2014 {attr.label}: "
            claims.append(
                ClaimDef(
                    cid=cid,
                    entity=ent,
                    attr=attr,
                    template_line=t_line,
                    v0=v0,
                    v1=v1,
                    source_pages=[],
                )
            )
    assert len(claims) == 20
    assert len({c.template_line for c in claims}) == 20

    # 4. Assign source_pages:
    # - Every content page receives at least 2 primary claims
    # - Exactly 6 claims (30%) appear on 2-3 pages (4 on 2 pages, 2 on 3 pages); 14 on 1 page
    entity_home_page: dict[str, str] = {}
    non_overview_files = page_filenames[1:]
    for idx_e, ent in enumerate(entities):
        entity_home_page[ent] = non_overview_files[idx_e % len(non_overview_files)]

    # Start by assigning each claim a primary page, ensuring every page gets >= 2 claims
    page_claim_map: dict[str, list[str]] = {fn: [] for fn in page_filenames}
    claim_pages_map: dict[str, list[str]] = {c.cid: [] for c in claims}

    # First guarantee every page gets at least 2 claims from the 20
    shuffled_claims = list(claims)
    set_rng.shuffle(shuffled_claims)
    assigned_cids: set[str] = set()
    for fn in page_filenames:
        for _ in range(2):
            # Prefer a claim whose entity's home matches fn, else take next unassigned
            pick = next(
                (c for c in shuffled_claims if c.cid not in assigned_cids and entity_home_page[c.entity] == fn),
                None,
            )
            if pick is None:
                pick = next(c for c in shuffled_claims if c.cid not in assigned_cids)
            assigned_cids.add(pick.cid)
            claim_pages_map[pick.cid].append(fn)
            page_claim_map[fn].append(pick.cid)

    # Assign remaining primary claims to their entity home page (or overview/operations for balance)
    for c in shuffled_claims:
        if c.cid in assigned_cids:
            continue
        home = entity_home_page[c.entity]
        # Keep page sizes balanced: if home already has >= 4 claims, pick lightest page
        if len(page_claim_map[home]) >= 4:
            target = min(page_filenames, key=lambda fn: (len(page_claim_map[fn]), page_filenames.index(fn)))
        else:
            target = home
        assigned_cids.add(c.cid)
        claim_pages_map[c.cid].append(target)
        page_claim_map[target].append(c.cid)

    # Now pick 6 claims (30%) to be multi-page: 4 appear on 2 pages, 2 appear on 3 pages
    multi_claims = set_rng.sample(claims, 6)
    overview_fn = page_filenames[0]
    for idx_m, c in enumerate(multi_claims):
        extra_needed = 2 if idx_m < 2 else 1  # 2 claims on 3 pages, 4 claims on 2 pages
        current = set(claim_pages_map[c.cid])
        candidates = [fn for fn in page_filenames if fn not in current]
        # Prefer overview page as the first secondary placement when available
        chosen_extras: list[str] = []
        if overview_fn in candidates:
            chosen_extras.append(overview_fn)
            candidates.remove(overview_fn)
        while len(chosen_extras) < extra_needed and candidates:
            # Prefer pages with fewer claims so density stays natural
            candidates.sort(key=lambda fn: (len(page_claim_map[fn]), set_rng.random()))
            pick_fn = candidates.pop(0)
            chosen_extras.append(pick_fn)
        for fn in chosen_extras:
            claim_pages_map[c.cid].append(fn)
            page_claim_map[fn].append(c.cid)

    # Sort each claim's source_pages in page_filenames order
    page_order = {fn: i for i, fn in enumerate(page_filenames)}
    claims_by_id = {c.cid: c for c in claims}
    for c in claims:
        c.source_pages = sorted(claim_pages_map[c.cid], key=lambda fn: page_order[fn])

    # 5. Build structured PageModels with distinct prose templates per claim appearance
    # Track which template indices have been used per claim so multi-page occurrences differ in wording!
    claim_tpl_order: dict[str, list[str]] = {}
    for c in claims:
        tpls = list(c.attr.templates)
        set_rng.shuffle(tpls)
        claim_tpl_order[c.cid] = tpls
    claim_tpl_cursor: dict[str, int] = {c.cid: 0 for c in claims}

    page_models: list[PageModel] = []
    for spec, fmt, fn in zip(selected_specs, page_fmts, page_filenames):
        intro_ctx = make_distractor_ctx(org_name, region, town, set_rng)
        intro_text = spec.intro.format(**intro_ctx)

        # Render all 4 variants of each noise block with fresh distractor contexts
        noise_variants: list[list[str]] = []
        for block_variants in spec.noise_blocks:
            rendered_vars: list[str] = []
            for v_tpl in block_variants:
                v_ctx = make_distractor_ctx(org_name, region, town, set_rng)
                rendered_vars.append(v_tpl.format(**v_ctx))
            # Guarantee all variants are strictly distinct
            assert len(set(rendered_vars)) == len(rendered_vars)
            noise_variants.append(rendered_vars)

        # Build claim slots for this page (shuffled order so claims don't appear in rigid entity order)
        cids_on_page = list(page_claim_map[fn])
        set_rng.shuffle(cids_on_page)
        comp_pool = list(domain.companion_sentences)
        set_rng.shuffle(comp_pool)
        slots: list[ClaimSlot] = []
        for slot_i, cid in enumerate(cids_on_page):
            cdef = claims_by_id[cid]
            tpl_idx = claim_tpl_cursor[cid] % len(claim_tpl_order[cid])
            claim_tpl_cursor[cid] += 1
            tpl = claim_tpl_order[cid][tpl_idx]
            s_ctx = make_distractor_ctx(org_name, region, town, set_rng)
            s_ctx["entity"] = cdef.entity
            comp_ctx = make_distractor_ctx(org_name, region, town, set_rng)
            comp_sent = comp_pool[slot_i % len(comp_pool)].format(**comp_ctx)
            slots.append(
                ClaimSlot(
                    cid=cid,
                    sentence_template=tpl,
                    ctx=s_ctx,
                    companion=comp_sent,
                )
            )

        # Include optional single small bullet list (~55% of pages)
        bullets: list[str] = []
        if spec.bullet_pool and set_rng.random() < 0.55:
            k_bul = min(len(spec.bullet_pool), set_rng.choice([2, 3]))
            for b_tpl in set_rng.sample(list(spec.bullet_pool), k_bul):
                b_ctx = make_distractor_ctx(org_name, region, town, set_rng)
                bullets.append(b_tpl.format(**b_ctx))

        page_models.append(
            PageModel(
                filename=fn,
                fmt=fmt,
                title=spec.title,
                description=spec.description,
                intro=intro_text,
                section_titles=choose_section_titles(spec, set_rng),
                noise_variants=noise_variants,
                claim_slots=slots,
                bullets=bullets,
            )
        )

    index_intro_ctx = make_distractor_ctx(org_name, region, town, set_rng)
    index_intro = set_rng.choice(domain.index_intros).format(**index_intro_ctx)
    index_text = render_index_page(index_filename, index_fmt, org_name, index_intro, page_models)

    # 6. Plan cycles 0..4 (cycle_1..cycle_4 shuffled multiset {F, F, N, Z})
    cycle_order = list(CYCLE_TYPES_MULTISET)
    set_rng.shuffle(cycle_order)

    truth_0 = {c.cid: c.v0 for c in claims}
    truth_history: list[dict[str, str]] = [dict(truth_0)]

    # noise_state[filename] = list of active variant index per noise block on that page
    noise_state: dict[str, list[int]] = {
        pm.filename: [0] * len(pm.noise_variants) for pm in page_models
    }
    noise_history: list[dict[str, list[int]]] = [
        {fn: list(idxs) for fn, idxs in noise_state.items()}
    ]

    used_changed_claims: set[str] = set()
    cycles_meta: list[dict] = []
    f_seen = 0

    def apply_noise_edit(fn: str) -> None:
        # Pick a noise block on fn that still has an unused variant (we have 3 blocks * 3 advances = 9 possible!)
        pm = next(p for p in page_models if p.filename == fn)
        avail = [
            i for i in range(len(pm.noise_variants))
            if noise_state[fn][i] + 1 < len(pm.noise_variants[i])
        ]
        assert avail, f"Exhausted noise variants on {fn}"
        blk_idx = set_rng.choice(avail)
        noise_state[fn][blk_idx] += 1

    for cyc_num, ctype in enumerate(cycle_order, start=1):
        cur_truth = dict(truth_history[-1])
        if ctype == "Z":
            changed_claims: list[str] = []
            noise_pages: list[str] = []
        elif ctype == "N":
            changed_claims = []
            n_noise = set_rng.choice([1, 2])
            chosen_noise = set_rng.sample(page_filenames, n_noise)
            chosen_noise.sort(key=lambda fn: page_order[fn])
            for fn in chosen_noise:
                apply_noise_edit(fn)
            noise_pages = chosen_noise
        elif ctype == "F":
            f_seen += 1
            remaining = [c for c in claims if c.cid not in used_changed_claims]
            multi_rem = [c for c in remaining if len(c.source_pages) >= 2]
            single_rem = [c for c in remaining if len(c.source_pages) == 1]

            # Choose 2 distinct unused claims leaving at least 1 content page disjoint for the noise edit.
            # On the first F cycle, prefer 1 multi-page + 1 single-page claim so multi-page updates are tested.
            pair: tuple[ClaimDef, ClaimDef] | None = None
            candidate_pairs: list[tuple[ClaimDef, ClaimDef]] = []
            if f_seen == 1 and multi_rem and single_rem:
                for cm in multi_rem:
                    for cs in single_rem:
                        covered = set(cm.source_pages) | set(cs.source_pages)
                        if len(covered) < len(page_filenames):
                            candidate_pairs.append((cm, cs))
            if not candidate_pairs:
                for i in range(len(remaining)):
                    for j in range(i + 1, len(remaining)):
                        c1, c2 = remaining[i], remaining[j]
                        covered = set(c1.source_pages) | set(c2.source_pages)
                        if len(covered) < len(page_filenames):
                            candidate_pairs.append((c1, c2))
            assert candidate_pairs, "Failed to find F-cycle claim pair with disjoint noise page"
            pair = set_rng.choice(candidate_pairs)

            c1, c2 = pair
            cur_truth[c1.cid] = c1.v1
            cur_truth[c2.cid] = c2.v1
            used_changed_claims.add(c1.cid)
            used_changed_claims.add(c2.cid)
            changed_claims = sorted([c1.cid, c2.cid])

            affected = set(c1.source_pages) | set(c2.source_pages)
            disjoint_pages = [fn for fn in page_filenames if fn not in affected]
            noise_fn = set_rng.choice(disjoint_pages)
            apply_noise_edit(noise_fn)
            noise_pages = [noise_fn]
        else:
            raise ValueError(f"Unknown cycle type: {ctype}")

        truth_history.append(cur_truth)
        noise_history.append({fn: list(idxs) for fn, idxs in noise_state.items()})
        cycles_meta.append(
            {
                "cycle": cyc_num,
                "type": ctype,
                "changed_claims": changed_claims,
                "noise_pages": noise_pages,
            }
        )

    # 7. Write template.md and all 5 cycle sites, computing sha256 per file
    set_dir.mkdir(parents=True, exist_ok=True)
    template_md = render_template_md(org_name, entities, claims)
    (set_dir / "template.md").write_text(template_md, encoding="utf-8")

    page_sha256_history: list[dict[str, str]] = []
    index_bytes = index_text.encode("utf-8")
    index_sha = hashlib.sha256(index_bytes).hexdigest()

    for cyc_idx in range(5):
        site_dir = set_dir / f"cycle_{cyc_idx}" / "site"
        site_dir.mkdir(parents=True, exist_ok=True)

        hashes: dict[str, str] = {}
        # Write index
        (site_dir / index_filename).write_bytes(index_bytes)
        hashes[index_filename] = index_sha

        cyc_truth = truth_history[cyc_idx]
        cyc_noise = noise_history[cyc_idx]
        for pm in page_models:
            rendered = render_content_page(
                pm, org_name, index_filename, cyc_truth, cyc_noise[pm.filename]
            )
            data = rendered.encode("utf-8")
            (site_dir / pm.filename).write_bytes(data)
            hashes[pm.filename] = hashlib.sha256(data).hexdigest()

        # Store deterministically ordered keys: index first, then content pages in order
        ordered_hashes = {index_filename: hashes[index_filename]}
        for fn in page_filenames:
            ordered_hashes[fn] = hashes[fn]
        page_sha256_history.append(ordered_hashes)

    return {
        "set": set_id,
        "domain": domain.slug,
        "index": index_filename,
        "pages": page_filenames,
        "claims": [
            {
                "id": c.cid,
                "entity": c.entity,
                "label": c.attr.label,
                "template_line": c.template_line,
                "source_pages": c.source_pages,
            }
            for c in claims
        ],
        "truth": truth_history,
        "cycles": cycles_meta,
        "page_sha256": page_sha256_history,
    }


def generate(seed: int, n_sets: int, out_dir: Path) -> None:
    if n_sets < 1:
        raise ValueError("--sets must be >= 1")

    if out_dir.exists():
        if not out_dir.is_dir():
            raise SystemExit(f"Error: output path exists and is not a directory: {out_dir}")
        if any(out_dir.iterdir()):
            raise SystemExit(f"Error: refusing to write into non-empty directory: {out_dir}")
    else:
        out_dir.mkdir(parents=True, exist_ok=True)

    master_rng = random.Random(seed)
    sets_dir = out_dir / "sets"
    sets_dir.mkdir(parents=True, exist_ok=True)

    # Shuffle domains in batches so every group of len(DOMAINS) covers all 10 domains cleanly
    domain_sequence: list[DomainSpec] = []
    while len(domain_sequence) < n_sets:
        batch = list(DOMAINS)
        master_rng.shuffle(batch)
        domain_sequence.extend(batch)

    sets_manifest: list[dict] = []
    for idx in range(n_sets):
        set_id = f"s{idx + 1:02d}"
        set_seed = master_rng.randrange(1 << 62)
        set_rng = random.Random(set_seed)
        domain = domain_sequence[idx]
        set_meta = build_set(set_id, domain, set_rng, sets_dir / set_id)
        sets_manifest.append(set_meta)

    manifest = {
        "schema": SCHEMA_VERSION,
        "generator": GENERATOR_NAME,
        "seed": seed,
        "n_sets": n_sets,
        "cycle_types": list(CYCLE_TYPES_MULTISET),
        "sets": sets_manifest,
    }

    manifest_text = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    manifest_bytes = manifest_text.encode("utf-8")
    (out_dir / "manifest.json").write_bytes(manifest_bytes)

    manifest_digest = hashlib.sha256(manifest_bytes).hexdigest()
    (out_dir / "manifest.sha256").write_text(f"{manifest_digest}\n", encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate deterministic synthetic web source sets for fact-report testing."
    )
    parser.add_argument("--seed", type=int, required=True, help="Deterministic integer RNG seed.")
    parser.add_argument("--sets", type=int, required=True, help="Number of sets to generate (>= 1).")
    parser.add_argument("--out", type=Path, required=True, help="Empty or non-existent output directory.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        generate(seed=args.seed, n_sets=args.sets, out_dir=args.out)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
