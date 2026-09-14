"""Reference solution for ow_20_slugify (gauge only; never enters a workspace)."""

import hashlib
import re
import unicodedata

NOT_SLUG = re.compile(r"[^a-z0-9]+")


def clean(title):
    """The slug a title would have if nothing else were in the batch.

    Accents are peeled off rather than dropped, so "Café" keeps its c-a-f-e.
    """
    folded = unicodedata.normalize("NFKD", title)
    folded = "".join(ch for ch in folded if not unicodedata.combining(ch))
    return NOT_SLUG.sub("-", folded.lower()).strip("-")


def fallback(title):
    """A title with nothing Latin in it still needs a usable, stable slug, so it
    gets one derived from the title itself rather than from its position."""
    return "t-" + hashlib.sha256(title.encode("utf-8")).hexdigest()[:8]


def slugify(titles):
    out = []
    taken = set()
    for title in titles:
        base = clean(title) or fallback(title)
        candidate = base
        number = 1
        while candidate in taken:
            number += 1
            candidate = "%s-%d" % (base, number)
        taken.add(candidate)
        out.append(candidate)
    return out
