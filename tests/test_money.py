import pytest

from money import to_cents


@pytest.mark.parametrize("value, expected", [
    ("1.235", 124),
    ("1.005", 101),
    ("0.015", 2),
    ("2.675", 268),
    ("1.234", 123),
    ("1.2349", 123),
    ("1.2350", 124),
    ("-1.235", -124),
    ("-0.005", -1),
    ("-1.234", -123),
    ("0", 0),
    ("10", 1000),
    ("19.99", 1999),
    (" 3.5 ", 350),
    ("1e2", 10000),
    ("123456789012345.675", 12345678901234568),
])
def test_to_cents(value, expected):
    assert to_cents(value) == expected


@pytest.mark.parametrize("value", ["", "abc", "NaN", "inf", "-Infinity"])
def test_invalid(value):
    with pytest.raises(ValueError):
        to_cents(value)
