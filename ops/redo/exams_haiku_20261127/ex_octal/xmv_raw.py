from octal import parse_octal


def test_zero_digit_gives_zero():
    # SRC: "Given an octal input string, your program should produce a decimal output."
    assert parse_octal('0') == 0


def test_single_digit_is_its_own_value():
    # SRC: "Given an octal input string, your program should produce a decimal output."
    assert parse_octal('7') == 7


def test_two_digit_power_of_eight():
    # SRC: "Octal is similar, but uses powers of 8 rather than powers of 10."
    assert parse_octal('10') == 8


def test_two_digit_value():
    # SRC: "Octal is similar, but uses powers of 8 rather than powers of 10."
    assert parse_octal('17') == 15


def test_example_233_positional_sum():
    # SRC: "= 2*8^2 + 3*8^1 + 3*8^0"
    assert parse_octal('233') == 2 * 64 + 3 * 8 + 3


def test_example_233_result():
    # SRC: "= 155"
    assert parse_octal('233') == 155


def test_all_sevens_three_digits():
    # SRC: "Octal is similar, but uses powers of 8 rather than powers of 10."
    assert parse_octal('777') == 511


def test_example_from_task_statement():
    # SRC: "Convert an octal number, represented as a string (e.g. '1735263'), to its decimal equivalent using first principles"
    assert parse_octal('1735263') == 506547


def test_six_digit_maximum_all_sevens():
    # SRC: "Octal is similar, but uses powers of 8 rather than powers of 10."
    assert parse_octal('777777') == 262143


def test_invalid_digit_eight_is_zero():
    # SRC: "Treat invalid input as octal 0."
    assert parse_octal('8') == 0


def test_invalid_digit_nine_is_zero():
    # SRC: "Treat invalid input as octal 0."
    assert parse_octal('9') == 0


def test_non_numeric_input_is_zero():
    # SRC: "Treat invalid input as octal 0."
    assert parse_octal('abc') == 0
