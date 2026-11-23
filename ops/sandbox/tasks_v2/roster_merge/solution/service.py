"""Identity-aware roster merger."""
import unicodedata
from checks import objects


def email_key(value):
    if not isinstance(value, str):
        raise ValueError("invalid email")
    email = unicodedata.normalize("NFC", value.strip()).casefold()
    if email.count("@") != 1 or not all(email.split("@")):
        raise ValueError("invalid email")
    return email


def role_list(value):
    if isinstance(value, str):
        value = value.split("|") if value else []
    roles = sorted({role.strip().lower() for role in value if role.strip()})
    if set(roles) - {"viewer", "editor", "admin"}:
        raise ValueError("invalid role")
    return roles


def merge_roster(existing, incoming, default_role="viewer"):
    default = role_list(default_role)
    rows = objects(existing) + objects(incoming)
    result = {}
    for row in rows:
        email = email_key(row.get("email"))
        name = row.get("name", "").strip()
        roles = role_list(row["roles"]) if "roles" in row else list(default)
        active = row.get("active", True)
        if not isinstance(active, bool):
            raise ValueError("invalid active")
        previous = result.get(email)
        if previous is None:
            result[email] = dict(email=email, name=name, roles=roles, active=active)
        else:
            previous["name"] = name or previous["name"]
            previous["roles"] = sorted(set(previous["roles"]) | set(roles))
            previous["active"] = active
    return list(result.values())


def active_users(rows):
    return [row for row in merge_roster(rows, []) if row["active"]]


def role_counts(rows):
    counts = {role: 0 for role in ("viewer", "editor", "admin")}
    for row in merge_roster(rows, []):
        for role in row["roles"]:
            counts[role] += 1
    return counts
