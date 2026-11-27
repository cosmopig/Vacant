from prime_factors import factors


def test_no_factors_for_one():
    assert factors(1) == []


def test_two_is_prime():
    assert factors(2) == [2]


def test_three_is_prime():
    assert factors(3) == [3]


def test_square_of_prime():
    assert factors(4) == [2, 2]


def test_product_of_two_distinct_primes():
    assert factors(6) == [2, 3]


def test_power_of_two():
    assert factors(8) == [2, 2, 2]


def test_square_of_odd_prime():
    assert factors(9) == [3, 3]


def test_power_of_three():
    assert factors(27) == [3, 3, 3]


def test_example_from_description():
    assert factors(60) == [2, 2, 3, 5]


def test_large_prime_is_its_own_factor():
    assert factors(97) == [97]


def test_repeated_prime_factors_of_composite():
    assert factors(900) == [2, 2, 3, 3, 5, 5]


def test_product_of_five_distinct_primes():
    assert factors(2310) == [2, 3, 5, 7, 11]
