"""Reference solution for ow_10_dedupe (gauge only; never enters a workspace)."""

POLICIES = ("first", "last", "merge")


def field_of(record, name):
    if name not in record:
        raise KeyError(name)
    return record[name]


def key_of(record, key):
    """One value for a single field, a tuple in the given order for a composite."""
    if isinstance(key, list):
        return tuple(field_of(record, name) for name in key)
    return field_of(record, key)


def merge_into(kept, incoming):
    # A later None is "not filled in", so it must not wipe out a value that was.
    for name, value in incoming.items():
        if value is not None:
            kept[name] = value


def dedupe(records, key, policy="first"):
    if policy not in POLICIES:
        raise ValueError("policy must be one of %s, got %r"
                         % (", ".join(POLICIES), policy))
    order = []
    kept = {}
    for record in records:
        identity = key_of(record, key)
        if identity not in kept:
            order.append(identity)
            kept[identity] = dict(record)
        elif policy == "last":
            kept[identity] = dict(record)
        elif policy == "merge":
            merge_into(kept[identity], record)
    return [kept[identity] for identity in order]
