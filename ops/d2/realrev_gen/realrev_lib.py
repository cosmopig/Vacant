"""Shared stdlib-only utilities for fetching, sanitizing, parsing, and checking
frozen English Wikipedia revision snapshots.
"""

from __future__ import annotations

import gzip
import hashlib
import html
import json
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

WIKI_API_URL = "https://en.wikipedia.org/w/api.php"
USER_AGENT = "d2-realrev-fetch/0.1 (offline research snapshot)"

CATEGORIES = (
    "Category:EFL League Two players",
    "Category:National League (English football) players",
    "Category:Scottish Professional Football League players",
)

MANIFEST_SCHEMA = "vacant.d2.manifest/1"
MANIFEST_GENERATOR = "realrev-wikipedia/1"
DOMAIN_NAME = "football biographies (Wikipedia)"
TEMPLATE_TITLE = "# Football biographies \u2014 verification report"
TEMPLATE_INSTRUCTION = "Fill each blank with the exact current value as shown on the site."
LICENSE_NOTE = "Text from English Wikipedia, CC BY-SA 4.0; revisions as listed"

VOID_ELEMENTS = frozenset(
    {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }
)

BLOCK_SPACE_TAGS = frozenset({"br", "p", "div", "li", "dt", "dd"})

EXCLUDED_LABEL_RE = re.compile(
    r"\b(?:date|birth|born|died|death|age|height)\b", re.IGNORECASE
)

YEAR_RANGE_RE = re.compile(
    r"^\s*\d{4}(?:\s*[\u2013\u2014\-−/]\s*(?:\d{2,4})?)?\s*$"
)

FULL_DATE_RE = re.compile(
    r"^(?:\d{1,2}\s+[A-Za-z]+\s+\d{4}|[A-Za-z]+\s+\d{1,2},?\s+\d{4}|\d{4}-\d{2}-\d{2})$"
)

PLAIN_INT_RE = re.compile(r"^\d+$")
APPS_GOALS_RE = re.compile(r"^\d+\s*\(\d+\)$")
WITH_UNIT_RE = re.compile(
    r"(?:(?:\d+(?:[.,]\d+)?)\s*(?:cm|mm|m|km|kg|g|lb|lbs|ft|in|st|%|mph|km/h|yrs?|years?|months?|days?)\b"
    r"|(?:[£$€]\s*\d))",
    re.IGNORECASE,
)


def parse_iso_utc(ts: str) -> datetime:
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    dt = datetime.fromisoformat(ts)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def format_iso_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def compute_timepoints(end_str: str, days: int) -> list[str]:
    if days <= 0:
        raise ValueError("days must be positive")
    end_dt = parse_iso_utc(end_str)
    step = timedelta(days=days) / 4
    return [format_iso_utc(end_dt - step * (4 - k)) for k in range(5)]


def normalize_ws(text: str) -> str:
    text = text.replace("\u200b", "").replace("\ufeff", "")
    return re.sub(r"\s+", " ", text).strip()


def slugify_title(title: str) -> str:
    decomposed = unicodedata.normalize("NFKD", title)
    ascii_str = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    lowered = ascii_str.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
    if not slug or slug == "index":
        slug = f"article-{hashlib.sha256(title.encode('utf-8')).hexdigest()[:8]}"
    return slug


def normalize_wiki_title(title: str) -> str:
    t = title.replace("_", " ").strip()
    if not t:
        return t
    return t[0].upper() + t[1:]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def classify_value_shape(value: str) -> str:
    v = normalize_ws(value)
    if PLAIN_INT_RE.match(v):
        return "plain integer"
    if APPS_GOALS_RE.match(v):
        return '"a (b)"'
    if WITH_UNIT_RE.search(v):
        return "with unit"
    return "other"


def wiki_permalink(title: str, revid: int) -> str:
    encoded = urllib.parse.quote(title.replace(" ", "_"), safe=":/()'")
    return f"https://en.wikipedia.org/w/index.php?title={encoded}&oldid={revid}"


class WikiClient:
    """Polite, rate-limited, cached MediaWiki API client (stdlib only)."""

    def __init__(
        self,
        cache_dir: Path,
        min_interval: float = 1.05,
        max_retries: int = 6,
    ) -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.min_interval = min_interval
        self.max_retries = max_retries
        self._last_request_ts = 0.0
        self.network_requests = 0
        self.cache_hits = 0

    def _cache_path(self, params: dict[str, Any]) -> Path:
        canonical = json.dumps(
            sorted((str(k), str(v)) for k, v in params.items()),
            separators=(",", ":"),
            ensure_ascii=True,
        )
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        sub = self.cache_dir / digest[:2]
        sub.mkdir(parents=True, exist_ok=True)
        return sub / f"{digest}.json"

    def query(self, params: dict[str, Any]) -> dict[str, Any]:
        full_params = {str(k): str(v) for k, v in params.items()}
        full_params.setdefault("format", "json")
        full_params.setdefault("formatversion", "2")

        cpath = self._cache_path(full_params)
        if cpath.exists():
            self.cache_hits += 1
            return json.loads(cpath.read_text(encoding="utf-8"))

        qs = urllib.parse.urlencode(sorted(full_params.items()))
        url = f"{WIKI_API_URL}?{qs}"
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
        }

        backoff = 2.0
        for attempt in range(self.max_retries + 1):
            now = time.monotonic()
            wait = self.min_interval - (now - self._last_request_ts)
            if wait > 0:
                time.sleep(wait)

            req = urllib.request.Request(url, headers=headers)
            self._last_request_ts = time.monotonic()
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    raw = resp.read()
                    if resp.headers.get("Content-Encoding", "").lower() == "gzip":
                        raw = gzip.decompress(raw)
                    self.network_requests += 1
                    data = json.loads(raw.decode("utf-8"))
                    tmp = cpath.with_suffix(".tmp")
                    tmp.write_text(
                        json.dumps(data, ensure_ascii=False), encoding="utf-8"
                    )
                    tmp.replace(cpath)
                    return data
            except urllib.error.HTTPError as exc:
                if exc.code in (429, 500, 502, 503, 504) and attempt < self.max_retries:
                    retry_after = exc.headers.get("Retry-After")
                    delay = backoff
                    if retry_after:
                        try:
                            delay = max(delay, float(retry_after))
                        except ValueError:
                            pass
                    print(
                        f"[WikiClient] HTTP {exc.code}, sleeping {delay:.1f}s (attempt {attempt + 1}/{self.max_retries})",
                        file=sys.stderr,
                        flush=True,
                    )
                    time.sleep(delay)
                    backoff = min(backoff * 2.0, 60.0)
                    continue
                raise
            except (urllib.error.URLError, TimeoutError, OSError):
                if attempt < self.max_retries:
                    time.sleep(backoff)
                    backoff = min(backoff * 2.0, 60.0)
                    continue
                raise

        raise RuntimeError(f"Exhausted retries for {url}")


def is_redirect_or_disambig(title: str, raw_html: str) -> bool:
    if "(disambiguation)" in title.lower():
        return True
    if 'class="redirectMsg"' in raw_html or "redirectText" in raw_html:
        return True
    if 'id="disambigbox"' in raw_html or "dmbox-disambig" in raw_html:
        return True
    return False


class _HTMLSanitizer(HTMLParser):
    """Strip <script> and <style> elements and rewrite same-set internal links."""

    def __init__(self, link_map: dict[str, str]) -> None:
        super().__init__(convert_charrefs=True)
        self.link_map = link_map
        self.out: list[str] = []
        self._drop_tag: str | None = None
        self._drop_depth = 0

    def _rewrite_href(self, href: str) -> str:
        if not href.startswith("/wiki/"):
            return href
        path_part, sep, frag = href[len("/wiki/") :].partition("#")
        target_title = normalize_wiki_title(urllib.parse.unquote(path_part))
        local = self.link_map.get(target_title)
        if not local:
            return href
        return f"{local}#{frag}" if sep else local

    def _format_attrs(self, tag: str, attrs: list[tuple[str, str | None]]) -> str:
        parts: list[str] = []
        for k, v in attrs:
            if v is None:
                parts.append(f" {k}")
            else:
                if tag == "a" and k.lower() == "href":
                    v = self._rewrite_href(v)
                parts.append(f' {k}="{html.escape(v, quote=True)}"')
        return "".join(parts)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        t = tag.lower()
        if self._drop_tag is not None:
            if t == self._drop_tag:
                self._drop_depth += 1
            return
        if t in ("script", "style"):
            self._drop_tag = t
            self._drop_depth = 1
            return
        self.out.append(f"<{t}{self._format_attrs(t, attrs)}>")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        t = tag.lower()
        if self._drop_tag is not None or t in ("script", "style"):
            return
        if t in VOID_ELEMENTS:
            self.out.append(f"<{t}{self._format_attrs(t, attrs)}>")
        else:
            self.out.append(f"<{t}{self._format_attrs(t, attrs)}></{t}>")

    def handle_endtag(self, tag: str) -> None:
        t = tag.lower()
        if self._drop_tag is not None:
            if t == self._drop_tag:
                self._drop_depth -= 1
                if self._drop_depth == 0:
                    self._drop_tag = None
            return
        if t in VOID_ELEMENTS:
            return
        self.out.append(f"</{t}>")

    def handle_data(self, data: str) -> None:
        if self._drop_tag is not None:
            return
        self.out.append(html.escape(data, quote=False))


def sanitize_html(raw_html: str, title: str, link_map: dict[str, str]) -> str:
    parser = _HTMLSanitizer(link_map)
    parser.feed(raw_html)
    parser.close()
    body = "".join(parser.out)
    safe_title = html.escape(title, quote=False)
    return (
        "<!DOCTYPE html>\n"
        f"<html><head><meta charset=\"utf-8\"><title>{safe_title}</title></head>"
        f"<body>{body}</body></html>\n"
    )


class _InfoboxParser(HTMLParser):
    """Extract direct rows and visible cell texts from the first table with class containing 'infobox'."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_infobox = False
        self.table_depth = 0
        self.done = False
        self.rows: list[list[tuple[str, str, str]]] = []
        self._cur_row: list[tuple[str, str, str]] | None = None
        self._cur_cell: tuple[str, str, list[str]] | None = None
        self._skip_stack: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self.done:
            return
        t = tag.lower()
        ad = {k.lower(): (v or "") for k, v in attrs}

        if t == "table":
            if not self.in_infobox:
                if "infobox" in ad.get("class", "").lower():
                    self.in_infobox = True
                    self.table_depth = 1
                return
            self.table_depth += 1
            return

        if not self.in_infobox or self.table_depth != 1:
            return

        if self._skip_stack:
            if t not in VOID_ELEMENTS:
                self._skip_stack.append(t)
            return

        style_compact = re.sub(r"\s+", "", ad.get("style", "").lower())
        cls_lower = ad.get("class", "").lower()
        if (
            t in ("script", "style")
            or "display:none" in style_compact
            or (t == "sup" and "reference" in cls_lower)
        ):
            if t not in VOID_ELEMENTS:
                self._skip_stack.append(t)
            return

        if t == "tr":
            self._cur_row = []
        elif t in ("th", "td") and self._cur_row is not None:
            self._cur_cell = (t, ad.get("class", ""), [])
        elif t in BLOCK_SPACE_TAGS and self._cur_cell is not None:
            self._cur_cell[2].append(" ")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self.done or not self.in_infobox or self.table_depth != 1 or self._skip_stack:
            return
        if tag.lower() in BLOCK_SPACE_TAGS and self._cur_cell is not None:
            self._cur_cell[2].append(" ")

    def handle_endtag(self, tag: str) -> None:
        if self.done or not self.in_infobox:
            return
        t = tag.lower()
        if t == "table":
            self.table_depth -= 1
            if self.table_depth == 0:
                self.in_infobox = False
                self.done = True
            return
        if self.table_depth != 1:
            return

        if self._skip_stack:
            if t in VOID_ELEMENTS:
                return
            if self._skip_stack[-1] == t:
                self._skip_stack.pop()
            elif t in self._skip_stack:
                while self._skip_stack and self._skip_stack[-1] != t:
                    self._skip_stack.pop()
                if self._skip_stack:
                    self._skip_stack.pop()
            return

        if t in ("th", "td") and self._cur_cell is not None and self._cur_row is not None:
            cell_text = normalize_ws("".join(self._cur_cell[2]))
            self._cur_row.append((self._cur_cell[0], self._cur_cell[1], cell_text))
            self._cur_cell = None
        elif t == "tr" and self._cur_row is not None:
            self.rows.append(self._cur_row)
            self._cur_row = None
        elif t in BLOCK_SPACE_TAGS and self._cur_cell is not None:
            self._cur_cell[2].append(" ")

    def handle_data(self, data: str) -> None:
        if (
            self.in_infobox
            and self.table_depth == 1
            and not self._skip_stack
            and self._cur_cell is not None
        ):
            self._cur_cell[2].append(data)


def _has_digit(s: str) -> bool:
    return any(ch.isdigit() for ch in s)


def extract_infobox_claims(html_text: str) -> list[tuple[str, str, str]]:
    """Parse the first infobox table and return [(label, value, row_text), ...] top-down.

    Duplicate labels within the same infobox are disambiguated by appending " (2)", " (3)", ...
    """
    parser = _InfoboxParser()
    parser.feed(html_text)
    parser.close()

    if not parser.rows:
        return []

    raw_claims: list[tuple[str, str, str]] = []
    current_section = ""

    for row in parser.rows:
        texts = [txt for _, _, txt in row]
        if len(row) == 1:
            if row[0][0] == "th" and texts[0]:
                current_section = texts[0].lower()
            continue

        if not any(_has_digit(t) for t in texts):
            continue

        row_text = normalize_ws(" ".join(t for t in texts if t))
        label = ""
        value = ""

        if len(row) == 4:
            c0, c1, c2, c3 = texts
            if not _has_digit(c2) and not _has_digit(c3):
                # Years-only row with empty/dash apps & goals
                continue
            non_stat = [x for x in (c0, c1) if x]
            if not non_stat:
                continue
            base_lbl = " ".join(non_stat)
            if EXCLUDED_LABEL_RE.search(base_lbl):
                continue
            if _has_digit(c2) and _has_digit(c3):
                value = normalize_ws(f"{c2} {c3}")
                label = f"{base_lbl} apps (goals)"
            elif _has_digit(c2):
                value = c2
                label = f"{base_lbl} apps"
            else:
                value = c3
                label = f"{base_lbl} (goals)"

        elif len(row) == 3:
            c0, c1, c2 = texts
            # Case A: e.g. Total | 342 | (121)
            if _has_digit(c1) and _has_digit(c2) and c2.startswith("(") and c2.endswith(")"):
                if not c0 or EXCLUDED_LABEL_RE.search(c0):
                    continue
                label = f"{c0} apps (goals)"
                value = normalize_ws(f"{c1} {c2}")
            # Case B: years | team | "45 (3)"
            elif _has_digit(c2):
                non_stat = [x for x in (c0, c1) if x]
                if not non_stat:
                    continue
                base_lbl = " ".join(non_stat)
                if EXCLUDED_LABEL_RE.search(base_lbl):
                    continue
                if APPS_GOALS_RE.match(c2):
                    label = f"{base_lbl} apps (goals)"
                else:
                    label = base_lbl
                value = c2
            else:
                continue

        elif len(row) == 2:
            lbl, val = texts
            if not lbl or not val:
                continue
            if EXCLUDED_LABEL_RE.search(lbl):
                continue
            if not _has_digit(val):
                # Years-only row (digits only in left cell)
                continue
            if YEAR_RANGE_RE.match(lbl) or YEAR_RANGE_RE.match(val):
                # Youth/managerial career years|team (even if team contains U18/1860) or years-active row
                continue
            if FULL_DATE_RE.match(val):
                continue
            if "youth" in current_section or "managerial" in current_section:
                continue
            label = lbl
            value = val
        else:
            continue

        label = normalize_ws(label)
        value = normalize_ws(value)
        if label and value:
            raw_claims.append((label, value, row_text))

    # Disambiguate duplicate labels top-down: first stays L, second becomes "L (2)", etc.
    counts: dict[str, int] = {}
    deduped: list[tuple[str, str, str]] = []
    for label, value, row_text in raw_claims:
        n = counts.get(label, 0) + 1
        counts[label] = n
        final_label = label if n == 1 else f"{label} ({n})"
        deduped.append((final_label, value, row_text))
    return deduped
