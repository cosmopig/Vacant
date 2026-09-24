import math
from collections import Counter

def countGoodIntegers(n: int, k: int) -> int:
    # A number is good if its digits can be rearranged to form a k-palindromic integer.
    # x is k-palindromic if it's a palindrome and divisible by k.
    # n <= 10, k <= 9.

    good_multisets = set()
    
    half_len = (n + 1) // 2
    for i in range(10**(half_len - 1), 10**half_len):
        s = str(i)
        # The first digit of the palindrome is s[0], which cannot be '0'.
        # But our loop starts from 10^(half_len-1), so i >= 10^(half_len-1).
        # If half_len=1, i ranges from 1 to 9. Correct.
        # If half_len=2, i ranges from 10 to 99. Correct.
        
        # Construct the palindrome
        if n % 2 == 0:
            # e.g., n=4, half_len=2, s="12" -> "1221"
            p_str = s + s[::-1]
        else:
            # e.g., n=3, half_len=2, s="12" -> "121"
            p_str = s + s[:-1][::-1]
            
        p_int = int(p_str)
        if p_int % k == 0:
            # This is a k-palindromic integer.
            # Its digits form a good multiset.
            good_multisets.add(tuple(sorted(list(p_str))))

    total_count = 0
    for ms in good_multisets:
        # Count unique n-digit numbers from this multiset (no leading zero)
        counts = Counter(ms)
        
        # Total permutations: n! / (c1! * c2! * ... * cm!)
        total_perms = math.factorial(n)
        for d in counts:
            total_perms //= math.factorial(counts[d])
            
        # Permutations starting with '0': (n-1)! / ((count(0)-1)! * c1! * ... * cm!)
        perms_starting_with_zero = 0
        if counts['0'] > 0:
            perms_starting_with_zero = math.factorial(n - 1)
            for d in counts:
                c = counts[d]
                if d == '0':
                    perms_starting_with_zero //= math.factorial(c - 1)
                else:
                    perms_starting_with_zero //= math.factorial(c)
        
        total_count += (total_perms - perms_starting_with_zero)

    return total_count
