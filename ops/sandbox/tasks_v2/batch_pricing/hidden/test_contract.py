import copy
import pytest
from service import quote, invoice
from codec import loads, dumps

def test_pricing_round_once_half_even_and_legacy():
    # SPEC §1
    # SPEC §2
    # SPEC §4
    tiers = [(1,"0.005"),(None,"0.005")]
    assert quote(2, tiers) == "0.01"
    assert quote(1, tiers) == "0.00"
    assert quote(3, tiers, "0.5") == "0.01"
    assert quote(0, tiers) == "0.00"
    old = loads('{"100":"1","20":"2","*":"0.5"}')
    assert quote(21, old) == "41.00"
    assert loads(dumps(old)) == old

def test_pricing_batch_order_coupons_and_total():
    # SPEC §3
    lines = [{"id":"z","quantity":1},{"id":"a","quantity":1,"coupon":"half"}]
    before = copy.deepcopy(lines)
    assert invoice(lines, [(None,"1.01")], {"half":"0.5"}) == {
        "lines":[{"id":"z","total":"1.01"},{"id":"a","total":"0.50"}],"total":"1.51"}
    assert lines == before
    assert invoice([], [(None,"1")]) == {"lines":[],"total":"0.00"}
    with pytest.raises(KeyError) as exc:
        invoice(lines, [(None,"1")], {})
    assert exc.value.args == ("half",)
    with pytest.raises(ValueError, match="^duplicate line id$"):
        invoice([{"id":"a","quantity":1}]*2, [(None,"1")])

def test_pricing_invalid_contracts():
    # SPEC §3
    for tiers in ([], [(1,"1")], [(None,"1"),(None,"2")], [(2,"1"),(1,"1"),(None,"1")], [(None,"NaN")]):
        with pytest.raises(ValueError, match="^invalid tiers$"):
            quote(1, tiers)
    with pytest.raises(ValueError, match="^invalid discount$"):
        quote(1, [(None,"1")], "1.1")
