def _palindromic_products(min_factor, max_factor):
    products = {}
    for a in range(min_factor, max_factor):
        for b in range(a, max_factor):
            product = a * b
            if str(product) == str(product)[::-1]:
                products.setdefault(product, set()).add((a, b))
    return products


def _check_range(min_factor, max_factor):
    if min_factor > max_factor:
        raise ValueError("min must be <= max")


def largest(max_factor, min_factor=0):
    """Find the largest palindrome product of two factors in the range.

    :return: tuple of (palindrome, set of factor pairs)
    """
    _check_range(min_factor, max_factor)
    products = _palindromic_products(min_factor, max_factor)
    if not products:
        raise ValueError("no palindrome products in range")
    value = max(products)
    return value, products[value]


def smallest(max_factor, min_factor=0):
    """Find the smallest palindrome product of two factors in the range.

    :return: tuple of (palindrome, set of factor pairs)
    """
    _check_range(min_factor, max_factor)
    products = _palindromic_products(min_factor, max_factor)
    if not products:
        raise ValueError("no palindrome products in range")
    value = min(products)
    return value, products[value]
