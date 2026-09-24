from collections import Counter
from math import factorial

def countGoodIntegers(n: int, k: int) -> int:
    # A number is good if its digits can be rearranged to form a k-palindromic integer.
    # A k-palindromic integer x must satisfy:
    # 1. x is a palindrome.
    # 2. x is divisible by k.
    # 3. x has no leading zeros (unless n=1 and x=0, but the problem says positive integers).

    unique_multisets = set()
    half_len = (n + 1) // 2
    start = 10**(half_len - 1)
    end = 10**half_len

    for i in range(start, end):
        s = str(i)
        if n % 2 == 0:
            res = s + s[::-1]
        else:
            res = s + s[:-1][::-1]
        
        val = int(res)
        if val % k == 0:
            # This is a k-palindromic integer. Its digits can be rearranged to form it.
            # Any number formed by these same digits will be "good".
            digits = sorted(list(res))
            unique_multisets.add(tuple(digits))

    total_count = 0
    for ms in unique_multisets:
        counts = [0] * 10
        for d in ms:
            counts[int(d)] += 1
        
        # Total permutations of the multiset
        total_perms = factorial(n)
        for c in counts:
            if c > 1:
                total_perms //= factorial(c)
        
        # Subtract permutations starting with '0'
        if counts[0] > 0:
            counts[0] -= 1
            sub_perms = factorial(n - 1)
            for c in counts:
                if c > 1:
                    sub_perms //= factorial(c)
            total_perms -= sub_perms
        
        total_count += total_perms

    return total_count
