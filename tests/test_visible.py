from service import Ledger

def test_transfer():
    ledger = Ledger({"a": 10, "b": 0})
    ledger.transfer("a", "b", 2)
    assert ledger.snapshot() == {"a": "8.00", "b": "2.00"}
