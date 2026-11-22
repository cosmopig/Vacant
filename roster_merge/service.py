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
    result = {}
    for row in objects(existing) + objects(incoming):
        email = row["email"].strip().lower()
        roles = role_list(row.get("roles", default_role))
        active = row.get("active", True)
        if not isinstance(active, bool):
            raise ValueError("invalid active")
        result[email] = {"email":email, "name":row.get("name", "").strip(),
                         "roles":roles, "active":active}
    return list(result.values())


def active_users(rows):
    return [row for row in merge_roster(rows, []) if row["active"]]


def role_counts(rows):
    counts = {role: 0 for role in ("viewer", "editor", "admin")}
    for row in merge_roster(rows, []):
        for role in row["roles"]:
            counts[role] += 1
    return counts
