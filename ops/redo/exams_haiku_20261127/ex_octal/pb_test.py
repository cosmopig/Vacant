from octal import parse_octal


def test_output_is_int_for_valid_input():
    """REQ: "Given an octal input string, your program should produce a decimal output."

    A valid octal string must produce an integer (not a bool, float or string).
    """
    result = parse_octal("233")
    assert isinstance(result, int)
    assert not isinstance(result, bool)


def test_example_233_octal_is_155():
    """REQ: "233 # octal = 2*8^2 + 3*8^1 + 3*8^0 = 2*64 + 3*8 + 3*1 = 128 + 24 + 3 = 155"

    The worked example in the requirements text: octal '233' equals decimal 155.
    """
    assert parse_octal("233") == 155


def test_example_1735263_octal_is_506547():
    """REQ: "Convert an octal number, represented as a string (e.g. '1735263'), to its decimal equivalent"

    Octal '1735263' = 1*8^6 + 7*8^5 + 3*8^4 + 5*8^3 + 2*8^2 + 6*8^1 + 3*8^0 = 506547.
    """
    assert parse_octal("1735263") == 506547


def test_single_octal_digits_map_to_themselves():
    """REQ: "Octal is similar, but uses powers of 8 rather than powers of 10."

    Each single octal digit 0 through 7 has the same decimal value.
    """
    expected = {"0": 0, "1": 1, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7}
    for digit, value in expected.items():
        assert parse_octal(digit) == value


def test_powers_of_eight_by_position():
    """REQ: "The nth number gets multiplied by 10^(n-1)." (applied with base 8, as in "uses powers of 8 rather than powers of 10")

    Position weights are powers of 8: '10' = 8, '20' = 16, '100' = 64, '1000' = 512, '777' = 511.
    """
    assert parse_octal("10") == 8
    assert parse_octal("20") == 16
    assert parse_octal("100") == 64
    assert parse_octal("1000") == 512
    assert parse_octal("777") == 511


def test_digit_order_matters():
    """REQ: "The rightmost digit gets multiplied by 10^0 = 1" (applied with base 8)

    Octal '12' = 1*8 + 2 = 10 and octal '21' = 2*8 + 1 = 17.
    """
    assert parse_octal("12") == 10
    assert parse_octal("21") == 17


def test_leading_zeros_do_not_change_value():
    """REQ: "All these values are summed."

    A leading zero contributes 0 to the sum, so leading zeros do not change the value:
    '0017' = 15, '00233' = 155, '0000' = 0.
    """
    assert parse_octal("0017") == 15
    assert parse_octal("00233") == 155
    assert parse_octal("0000") == 0


def test_appending_zero_multiplies_by_eight():
    """REQ: "Octal is similar, but uses powers of 8 rather than powers of 10."

    Appending a trailing octal zero multiplies the value by 8: '2330' = 8 * 155 = 1240,
    and '17352630' = 8 * 506547 = 4052376.
    """
    assert parse_octal("2330") == 1240
    assert parse_octal("17352630") == 4052376


def test_long_all_sevens_input():
    """REQ: "Octal is similar, but uses powers of 8 rather than powers of 10."

    Twenty-two octal sevens equal 8^22 - 1 = 2^66 - 1 = 73786976294838206463.
    """
    assert parse_octal("7" * 22) == 73786976294838206463


def test_digits_8_and_9_are_invalid_and_give_zero():
    """REQ: "Treat invalid input as octal 0."

    The characters '8' and '9' are not octal digits, so any input containing them gives 0.
    """
    assert parse_octal("8") == 0
    assert parse_octal("9") == 0
    assert parse_octal("18") == 0
    assert parse_octal("79") == 0
    assert parse_octal("90") == 0


def test_non_digit_characters_are_invalid_and_give_zero():
    """REQ: "Treat invalid input as octal 0."

    Inputs containing letters, a decimal point, or a minus sign are invalid and give 0.
    """
    assert parse_octal("abc") == 0
    assert parse_octal("x") == 0
    assert parse_octal("17a") == 0
    assert parse_octal("12.3") == 0
    assert parse_octal("-7") == 0


def test_empty_string_is_invalid_and_gives_zero():
    """REQ: "Treat invalid input as octal 0."

    An empty string is not a valid octal number, so it gives 0.
    """
    assert parse_octal("") == 0


def test_invalid_input_result_is_int():
    """REQ: "Treat invalid input as octal 0."

    The value returned for invalid input is the integer 0.
    """
    for bad in ["8", "abc", "", "-7"]:
        result = parse_octal(bad)
        assert isinstance(result, int)
        assert not isinstance(result, bool)
        assert result == 0


def test_valid_inputs_give_non_negative_results():
    """REQ: "Given an octal input string, your program should produce a decimal output."

    Valid octal strings contain only non-negative digit values, so their decimal results are non-negative.
    """
    for good in ["0", "7", "233", "1735263"]:
        assert parse_octal(good) >= 0
