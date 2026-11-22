import copy
import pytest
from service import merge_roster, role_counts
from codec import dumps, loads, load, save

def test_roster_unicode_order_roles_and_inactivity():
    # SPEC §1
    # SPEC §2
    # SPEC §3
    existing = [{"email":" STRAßE@EXAMPLE.COM ","name":"First","roles":["editor"]}, {"email":"z@b","roles":[]}]
    incoming = [{"email":"strasse@example.com","name":" ","roles":"ADMIN|editor","active":False}]
    before = copy.deepcopy((existing, incoming))
    merged = merge_roster(existing, incoming)
    assert [row["email"] for row in merged] == ["strasse@example.com","z@b"]
    assert merged[0] == {"email":"strasse@example.com","name":"First","roles":["admin","editor"],"active":False}
    assert merged[1]["roles"] == []
    merged[0]["roles"].append("viewer")
    assert (existing, incoming) == before
    assert role_counts(existing)["editor"] == 1

def test_roster_quoted_csv_legacy_and_empty():
    # SPEC §4
    # SPEC §3
    rows = merge_roster([], [{"email":"a@b","name":"Zoë, Z","roles":[]}])
    raw = dumps(rows)
    assert raw.startswith("email,name,roles,active\n")
    assert "\r" not in raw
    assert loads(raw) == rows
    assert loads("email,name\na@b,Old\n")[0]["roles"] == ["viewer"]
    assert merge_roster([], []) == []

def test_roster_exact_validation_errors():
    # SPEC §3
    for row, message in [({"email":"bad"},"invalid email"),
                         ({"email":"a@b","roles":["owner"]},"invalid role"),
                         ({"email":"a@b","active":1},"invalid active")]:
        with pytest.raises(ValueError, match="^"+message+"$"):
            merge_roster([], [row])

def test_roster_csv_preserves_embedded_carriage_returns(tmp_path):
    # SPEC §4
    rows = [{"email":"a@b", "name":"A\rB\r\nC\nD", "roles":[], "active":True}]
    encoded = dumps(rows)
    assert loads(encoded) == rows
    assert encoded.endswith("\n") and not encoded.endswith("\r\n")
    save(rows, tmp_path/"roster.csv")
    assert (tmp_path/"roster.csv").read_bytes() == encoded.encode("utf-8")
    assert load(tmp_path/"roster.csv") == rows
