"""Known-bad A: a set of seen keys and the caller's own dictionaries.

Deduplicating with a set is the first thing that works; it loses the policies, it
hands back the very objects it was given, and it sorts the result because the set
made the order look arbitrary anyway.
"""


def dedupe(records, key, policy="first"):
    seen = set()
    out = []
    for record in records:
        identity = record.get(key) if isinstance(key, str) else tuple(
            record.get(name) for name in key)
        if identity in seen:
            continue
        seen.add(identity)
        out.append(record)
    out.sort(key=lambda record: str(sorted(record.items())))
    return out
