"""Known-bad B: the closest near miss.

All three kinds are recognised. What is wrong: a line holding a secret is thrown
away entirely rather than having the secret taken out of it, and the report stops at
the first thing it finds, so the dashboard undercounts.
"""

import re

PATTERNS = [re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
            re.compile(r"(?i)authorization:\s*bearer\s+(\S+)"),
            re.compile(r"[A-Za-z][A-Za-z0-9+.\-]*://[^:/\s@]+:([^@/\s]+)@")]


def _hits(text):
    out = []
    for pattern in PATTERNS:
        for match in pattern.finditer(text):
            out.append(match.group(match.re.groups))
    return out


def redact(text):
    return "[redacted]" if _hits(text) else text


def findings(text):
    hits = _hits(text)
    return hits[:1]
