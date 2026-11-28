from octal import parse_octal


def test_zero():
    assert parse_octal("0") == 0


def test_single_digits():
    assert parse_octal("1") == 1
    assert parse_octal("7") == 7


def test_two_digit_octal_10_is_eight():
    assert parse_octal("10") == 8


def test_three_digit_octal_100_is_sixty_four():
    assert parse_octal("100") == 64


def test_worked_example_233_is_155():
    assert parse_octal("233") == 155


def test_all_sevens_three_digits_is_511():
    assert parse_octal("777") == 511


def test_leading_zeros_do_not_change_value():
    assert parse_octal("00") == 0
    assert parse_octal("0777") == 511


def test_longer_number():
    assert parse_octal("1735263") == 506547


def test_digit_8_is_invalid_and_treated_as_zero():
    assert parse_octal("8") == 0
    assert parse_octal("18") == 0


def test_digit_9_is_invalid_and_treated_as_zero():
    assert parse_octal("9") == 0
    assert parse_octal("79") == 0


def test_letters_are_invalid_and_treated_as_zero():
    assert parse_octal("1a") == 0
    assert parse_octal("17x") == 0
