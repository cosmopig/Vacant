import math

from prime_factors import factors


def test_one_has_no_prime_factors():
    # SRC: "Note that 1 is not a prime number."
    assert factors(1) == []


def test_prime_number_is_its_own_only_factor():
    # SRC: "A prime number is only evenly divisible by itself and 1."
    assert factors(2) == [2]


def test_odd_prime_is_its_own_only_factor():
    # SRC: "A prime number is only evenly divisible by itself and 1."
    assert factors(3) == [3]


def test_larger_prime_is_its_own_only_factor():
    # SRC: "A prime number is only evenly divisible by itself and 1."
    assert factors(97) == [97]


def test_first_division_removes_a_two():
    # SRC: "2 goes into 60, leaving 30."
    assert factors(30) == [2, 3, 5]


def test_repeated_prime_factor_is_listed_each_time():
    # SRC: "Compute the prime factors of a given natural number."
    assert factors(9) == [3, 3]


def test_power_of_two_lists_two_repeatedly():
    # SRC: "Compute the prime factors of a given natural number."
    assert factors(1024) == [2, 2, 2, 2, 2, 2, 2, 2, 2, 2]


def test_example_from_requirements():
    # SRC: "What are the prime factors of 60?"
    assert factors(60) == [2, 2, 3, 5]


def test_example_factors_are_the_successful_divisors():
    # SRC: "Our successful divisors in that computation represent the list of prime factors of 60: 2, 2, 3, and 5."
    assert factors(60) == [2, 2, 3, 5]


def test_product_of_factors_equals_original_number():
    # SRC: "= 60"
    assert math.prod(factors(60)) == 60


def test_mixed_repeated_factors():
    # SRC: "Our successful divisors in that computation represent the list of prime factors of 60: 2, 2, 3, and 5."
    assert factors(90) == [2, 3, 3, 5]


def test_last_remainder_is_one_and_process_ends():
    # SRC: "We're left only with 1, so now, we're done."
    assert factors(1001) == [7, 11, 13]
