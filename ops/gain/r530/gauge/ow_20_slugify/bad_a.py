"""Known-bad A: clean each title, hand back the list.

Nothing looks at whether two titles produced the same slug, and a title with no
Latin letters in it produces an empty string.
"""

import re


def slugify(titles):
    return [re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") for title in titles]
