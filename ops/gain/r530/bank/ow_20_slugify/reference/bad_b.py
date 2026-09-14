"""Known-bad B: the closest near miss.

Cleaning, deduplication and a fallback are all there. What is wrong: the collision
suffix is random, so the same batch gives different slugs each time, and only the
leading hyphens are stripped, so a title ending in punctuation keeps a trailing one.
"""

import re
import uuid


def slugify(titles):
    out = []
    taken = set()
    for title in titles:
        base = re.sub(r"[^a-z0-9]+", "-", title.lower()).lstrip("-")
        if not base:
            base = "post"
        candidate = base
        while candidate in taken:
            candidate = "%s-%s" % (base, uuid.uuid4().hex[:6])
        taken.add(candidate)
        out.append(candidate)
    return out
