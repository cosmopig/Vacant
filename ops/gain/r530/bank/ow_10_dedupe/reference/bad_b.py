"""Known-bad B: the policies are right, four smaller things are not.

The composite key is built by gluing the parts together with no separator, a
missing field quietly becomes None, a later None overwrites a real value under
merge, and the result shares dictionaries with the input.
"""

POLICIES = ("first", "last", "merge")


def dedupe(records, key, policy="first"):
    if policy not in POLICIES:
        raise ValueError("bad policy")
    order = []
    kept = {}
    for record in records:
        if isinstance(key, list):
            identity = "".join(str(record.get(name)) for name in key)
        else:
            identity = record.get(key)
        if identity not in kept:
            order.append(identity)
            kept[identity] = record
        elif policy == "last":
            kept[identity] = record
        elif policy == "merge":
            merged = dict(kept[identity])
            merged.update(record)
            kept[identity] = merged
    return [kept[identity] for identity in order]
