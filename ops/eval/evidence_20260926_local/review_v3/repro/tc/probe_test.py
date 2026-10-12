import json
from tests.test_zero_budget import *  # noqa
from tests.test_zero_budget import proj  # fixture

def test_probe_last_turn(proj):
    a = Pi(proj); a.ask()
    a.bash("python3 bad.py", "Traceback (most recent call last):\nValueError: bad")
    d = a.ev("stop", final_text="Done.", turn=14, budget=15)
    rv = [e for e in Recorder(proj).events() if e["type"] == "review"]
    print("REVIEW", json.dumps([{k: e.get(k) for k in ("sent","action","turns_left")} for e in rv]))
    dj = json.loads((Recorder(proj).dir / "delivery.json").read_text())
    print("DELIVERY_KEYS", list(dj)[:20])
    print("REASON", d["reason"])

def test_probe_last_turn_nobudget(proj):
    a = Pi(proj); a.ask()
    a.bash("python3 bad.py", "Traceback (most recent call last):\nValueError: bad")
    d = a.ev("stop", final_text="Done.")
    print("REASON_NOBUDGET", d["reason"])

def test_probe_given(proj):
    a = Pi(proj)
    a.ask("Read data/sales.csv and write the total to data/sales.csv's summary in /app/total.md.")
    a.bash("head data/sales.csv", SALES)
    d = a.turn(13)
    print("GIVEN", d["reason"])
