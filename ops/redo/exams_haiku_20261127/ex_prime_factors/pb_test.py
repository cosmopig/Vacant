import math

from prime_factors import factors


def _is_prime(n):
    """Trial-division primality check used only to verify returned factors."""
    if n < 2:
        return False
    d = 2
    while d * d <= n:
        if n % d == 0:
            return False
        d += 1
    return True


def test_returns_list():
    """REQ: "Our successful divisors in that computation represent the list of prime factors of 60: 2, 2, 3, and 5." """
    assert isinstance(factors(60), list)


def test_elements_are_ints():
    """REQ: "Compute the prime factors of a given natural number." """
    for value in factors(60):
        assert isinstance(value, int)
        assert not isinstance(value, bool)


def test_example_60():
    """REQ: "What are the prime factors of 60?" """
    assert factors(60) == [2, 2, 3, 5]


def test_factors_multiply_to_input():
    """REQ: "You can check this yourself:" """
    for n in (8, 60, 104929, 2310):
        assert math.prod(factors(n)) == n


def test_every_factor_is_prime():
    """REQ: "A prime number is only evenly divisible by itself and 1." """
    for n in (60, 2310, 104929):
        for f in factors(n):
            assert _is_prime(f), f"{f} returned for {n} is not prime"


def test_one_has_no_prime_factors():
    """REQ: "Note that 1 is not a prime number." """
    assert factors(1) == []


def test_prime_is_its_own_only_factor():
    """REQ: "A prime number is only evenly divisible by itself and 1." """
    assert factors(2) == [2]
    assert factors(97) == [97]


def test_repeated_factors_listed_with_multiplicity():
    """REQ: "Our successful divisors in that computation represent the list of prime factors of 60: 2, 2, 3, and 5." """
    assert factors(8) == [2, 2, 2]
    assert factors(2 ** 20) == [2] * 20


def test_composite_divisors_are_not_listed():
    """REQ: "The next possible factor is 4. 4 does not go cleanly into 5." """
    result = factors(12)
    assert result == [2, 2, 3]
    assert 4 not in result
    assert 6 not in result


def test_factors_in_ascending_order():
    """REQ: "Our first divisor is 2." """
    result = factors(2310)
    assert result == [2, 3, 5, 7, 11]
    assert result == sorted(result)


def test_two_prime_factors_of_semiprime():
    """REQ: "Compute the prime factors of a given natural number." """
    assert factors(104929) == [11, 9539]
