import pytest

from duration import parse_duration


@pytest.mark.parametrize(
    "text, expected",
    [
        ("0s", 0),
        ("5s", 5),
        ("2m", 120),
        ("1h", 3600),
        ("1h 30m", 5400),
        ("2m5s", 125),
        ("1h2m3s", 3723),
        ("1h 2m 3s", 3723),
        ("  1h  30m  ", 5400),
        ("\t1h\n30m\n", 5400),
        ("90m", 5400),
        ("007s", 7),
        ("0h0m0s", 0),
        ("30m 1h", 5400),
        ("1m 1m", 120),
        ("100000h", 360000000),
    ],
)
def test_valid(text, expected):
    assert parse_duration(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "",
        " ",
        "\n\t",
        "1",
        "h",
        "1x",
        "1H",
        "1 h",
        "-1s",
        "+1s",
        "1.5h",
        "1h,30m",
        "1h-30m",
        "1h 30",
        "abc",
        "1hm",
        "1h s",
        "١s",
        "1ｓ",
    ],
)
def test_malformed_raises_value_error(text):
    with pytest.raises(ValueError):
        parse_duration(text)


@pytest.mark.parametrize("value", [None, 5, b"1h"])
def test_non_string_raises_value_error(value):
    with pytest.raises(ValueError):
        parse_duration(value)
