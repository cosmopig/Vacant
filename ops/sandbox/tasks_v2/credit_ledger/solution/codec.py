"""Stable JSON snapshots, including the legacy flat mapping."""
import json
from service import Ledger, money


def dumps(ledger):
    payload = {"version": 2, "balances": ledger.snapshot(), "keys": ledger.history()}
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def loads(raw):
    payload = json.loads(raw)
    if payload.get("version") == 2:
        ledger = Ledger(payload["balances"])
        ledger._keys = {key: (a, b, money(value))
                        for key, (a, b, value) in payload.get("keys", {}).items()}
    else:
        ledger = Ledger(payload)
    return ledger


def save(ledger, path):
    from pathlib import Path
    Path(path).write_text(dumps(ledger), encoding="utf-8")


def load(path):
    from pathlib import Path
    return loads(Path(path).read_text(encoding="utf-8"))
