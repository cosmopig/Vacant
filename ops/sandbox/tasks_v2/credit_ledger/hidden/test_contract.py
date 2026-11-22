from decimal import Decimal
import pytest
from service import Ledger
from codec import dumps, loads

def test_ledger_cached_total_and_rounding():
    # SPEC §1
    # SPEC §2
    ledger = Ledger({"a": 10, "b": 0})
    assert ledger.total() == 10
    ledger.transfer("a", "b", "1.005")
    assert ledger.balance("a") == Decimal("9.00")
    assert ledger.balance("b") == Decimal("1.00")

def test_ledger_key_roundtrip_conflict_and_legacy():
    # SPEC §3
    # SPEC §4
    ledger = loads('{"a":"10","b":"0"}')
    ledger.transfer("a", "b", 2, key="x")
    ledger = loads(dumps(ledger))
    ledger.transfer("a", "b", "2.004", key="x")
    assert ledger.snapshot() == {"a": "8.00", "b": "2.00"}
    with pytest.raises(ValueError, match="^key conflict$"):
        ledger.transfer("a", "b", 3, key="x")
    snap = ledger.snapshot()
    snap["a"] = "bad"
    assert ledger.snapshot()["a"] == "8.00"

def test_ledger_atomic_rejection_and_retry():
    # SPEC §2
    # SPEC §3
    ledger = Ledger({"a": 2, "b": 5})
    with pytest.raises(ValueError, match="^insufficient funds$"):
        ledger.transfer("a", "b", 3, key="retry")
    ledger.transfer("b", "a", 2)
    ledger.transfer("a", "b", 3, key="retry")
    assert ledger.snapshot() == {"a": "1.00", "b": "6.00"}
    with pytest.raises(ValueError, match="^amount must be positive$"):
        ledger.transfer("a", "b", "0.001")
    with pytest.raises(KeyError) as exc:
        ledger.transfer("missing", "b", 1)
    assert exc.value.args == ("missing",)
    with pytest.raises(ValueError, match="^accounts must differ$"):
        ledger.transfer("a", "a", 1)
