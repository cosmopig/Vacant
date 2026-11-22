from collections import defaultdict
from copy import deepcopy
from decimal import ROUND_UP, localcontext

import pytest

from codec import dumps, loads
from service import invoice, quote


def test_quote_rounds_once_after_applying_discount():
    tiers = [(2, "0.005"), (None, "0.005")]
    assert quote(0, tiers) == "0.00"
    assert quote(3, tiers) == "0.02"
    assert quote(3, tiers, "0.7") == "0.00"
    assert quote(3, tiers, "1") == "0.00"


def test_invoice_preserves_order_and_sums_rounded_lines():
    tiers = [(None, "0.015")]
    lines = [{"id": "b", "quantity": 1}, {"id": "a", "quantity": 1, "coupon": "HALF"}]
    coupons = {"HALF": "0.5"}
    original = deepcopy((lines, tiers, coupons))
    assert invoice(lines, tiers, coupons) == {
        "lines": [{"id": "b", "total": "0.02"}, {"id": "a", "total": "0.01"}],
        "total": "0.03",
    }
    assert (lines, tiers, coupons) == original
    assert invoice([], tiers) == {"lines": [], "total": "0.00"}


def test_invoice_rejects_duplicate_ids_without_mutating_rows():
    lines = [{"id": "a", "quantity": 1}, {"id": "a", "quantity": 0}]
    original = deepcopy(lines)
    with pytest.raises(ValueError, match="^duplicate line id$"):
        invoice(lines, [(None, "1")])
    assert lines == original


def test_missing_coupon_does_not_create_a_default():
    coupons = defaultdict(lambda: "0.1")
    with pytest.raises(KeyError) as error:
        invoice([{"id": "a", "quantity": 1, "coupon": "unknown"}], [(None, "1")], coupons)
    assert error.value.args == ("unknown",)
    assert not coupons


@pytest.mark.parametrize("discount", [True, "NaN", "Infinity", "-0.01", "1.01", "invalid"])
def test_invalid_discount(discount):
    with pytest.raises(ValueError, match="^invalid discount$"):
        quote(1, [(None, "1")], discount)


@pytest.mark.parametrize("tiers", [[], [(1, "1")], [(True, "1"), (None, "2")], [(None, "-1")]])
def test_invalid_tiers(tiers):
    with pytest.raises(ValueError, match="^invalid tiers$"):
        quote(1, tiers)


def test_bool_quantity_is_not_an_integer():
    with pytest.raises(ValueError):
        quote(True, [(None, "1")])


def test_legacy_tiers_sort_numerically_and_round_trip():
    tiers = loads('{"*":"1","10":"2","2":"3"}')
    assert tiers == [(2, "3"), (10, "2"), (None, "1")]
    assert loads(dumps(tiers)) == tiers
    assert quote(11, tiers) == "23.00"


def test_numeric_wire_rate_keeps_decimal_precision():
    tiers = loads('[[null, 0.0050000000000000001]]')
    assert quote(1, tiers) == "0.01"


def test_decimal_precision_is_independent_of_callers_context():
    tiers = [(None, "123456789012345678901234567890.025")]
    lines = [{"id": "a", "quantity": 1}, {"id": "b", "quantity": 1}]
    with localcontext() as context:
        context.prec = 5
        context.rounding = ROUND_UP
        assert quote(1, tiers) == "123456789012345678901234567890.02"
        assert invoice(lines, tiers)["total"] == "246913578024691357802469135780.04"
