"""Known-bad A: only the access key.

The first pattern anyone writes, because it is the one that looks like a secret.
Bearer tokens and passwords in connection strings go straight through.
"""

import re

ACCESS_KEY = re.compile(r"\bAKIA[0-9A-Z]{16}\b")


def redact(text):
    return ACCESS_KEY.sub("[redacted]", text)


def findings(text):
    return ACCESS_KEY.findall(text)
