"""Reference solution for ow_19_redact (gauge only; never enters a workspace)."""

import re

MASK = "[redacted]"

#: (name, pattern, index of the group that is the secret). The group before it, if
#: any, is kept so the line still reads: "Authorization: Bearer [redacted]".
ACCESS_KEY = ("aws_access_key_id", re.compile(r"\bAKIA[0-9A-Z]{16}\b"), 0)
BEARER = ("bearer_token", re.compile(r"(?i)(authorization:\s*bearer\s+)(\S+)"), 2)
URL_PASSWORD = ("url_password",
                re.compile(r"([A-Za-z][A-Za-z0-9+.\-]*://[^:/\s@]+):([^@/\s]+)@"), 2)

KINDS = (ACCESS_KEY, BEARER, URL_PASSWORD)


def _mask(found, group):
    """Rebuild the match with only the secret group replaced."""
    if group == 0:
        return MASK
    text = found.group(0)
    start, end = found.span(group)
    offset = found.start()
    return text[:start - offset] + MASK + text[end - offset:]


def redact(text):
    out = text
    for _name, pattern, group in KINDS:
        out = pattern.sub(lambda found, group=group: _mask(found, group), out)
    return out


def findings(text):
    found = []
    for _name, pattern, group in KINDS:
        for match in pattern.finditer(text):
            found.append(match.group(group))
    return found
