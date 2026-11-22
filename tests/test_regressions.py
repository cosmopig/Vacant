from decimal import Decimal
from service import Ledger
import codec


def test_rounding_cache_idempotency_and_reload():
    l=Ledger({"a":10,"b":0})
    l.balance("a"); l.balance("b")
    l.transfer("a","b","0.125","k")
    assert l.balance("a")==Decimal("9.88") and l.balance("b")==Decimal("0.12"), (l.balance("a"),l.balance("b"))
    assert l.total()==Decimal("10.00")
    l.transfer("a","b",0.125,"k")
    assert l.balance("b")==Decimal("0.12")
    try: l.transfer("a","b",1,"k"); raise AssertionError("no conflict")
    except ValueError as e: assert str(e)=="key conflict"
    try: l.transfer("a","b",100,"x")
    except ValueError as e: assert str(e)=="insufficient funds"
    l.transfer("a","b",1,"x")
    try: l.transfer("a","b","0.004")
    except ValueError as e: assert str(e)=="amount must be positive"
    r=codec.loads(codec.dumps(l))
    assert r.snapshot()==l.snapshot() and r.history()==l.history(), (r.history(),l.history())
    assert codec.dumps(r)==codec.dumps(l)
    r.transfer("a","b",1,"x")  # replay no-op after reload
    assert r.snapshot()==l.snapshot()
    try: r.transfer("a","b",2,"x"); raise AssertionError("no conflict after reload")
    except ValueError: pass
    assert codec.loads('{"a":"1.5","b":2}').snapshot()=={"a":"1.50","b":"2.00"}
    h=l.history(); h["k"][0]="zz"; assert l.history()["k"][0]=="a"

