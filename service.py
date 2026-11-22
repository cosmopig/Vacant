"""Identity-aware roster merger."""
import unicodedata
from checks import objects

ROLES = ("viewer", "editor", "admin")


def email_key(value):
    if not isinstance(value, str):
        raise ValueError("invalid email")
    email = unicodedata.normalize("NFC", value).strip().casefold()
    if email.count("@") != 1 or not all(email.split("@")):
        raise ValueError("invalid email")
    return email


def role_list(value):
    if isinstance(value, str):
        value = value.split("|")
    elif not isinstance(value, (list, tuple)):
        raise ValueError("invalid role")
    if any(not isinstance(role, str) for role in value):
        raise ValueError("invalid role")
    roles = sorted({role.strip().lower() for role in value if role.strip()})
    if set(roles) - set(ROLES):
        raise ValueError("invalid role")
    return roles


def _name(value):
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValueError("invalid name")
    return value.strip()


def merge_roster(existing, incoming, default_role="viewer"):
    defaults = role_list([default_role])
    rows = objects([] if existing is None else existing, "existing")
    rows += objects([] if incoming is None else incoming, "incoming")
    result = {}
    for row in rows:
        email = email_key(row.get("email"))
        roles = row.get("roles")
        roles = list(defaults) if roles is None else role_list(roles)
        active = row.get("active", True)
        if not isinstance(active, bool):
            raise ValueError("invalid active")
        name = _name(row.get("name"))
        previous = result.get(email)
        if previous is not None:
            name = name or previous["name"]
            roles = sorted(set(roles) | set(previous["roles"]))
        result[email] = {"email": email, "name": name, "roles": roles, "active": active}
    return list(result.values())


def active_users(rows):
    return [row for row in merge_roster(rows, []) if row["active"]]


def role_counts(rows):
    counts = {role: 0 for role in ROLES}
    for row in merge_roster(rows, []):
        for role in row["roles"]:
            counts[role] += 1
    return counts
