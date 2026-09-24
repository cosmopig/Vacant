from collections import Counter
import math

def countGoodIntegers(n: int, k: int) -> int:
    # A "good" integer has digits that can be rearranged into a k-palindromic integer.
    # A k-palindromic integer x must:
    # 1. Be a palindrome.
    # 2. Be divisible by k.
    # 3. Have n digits (no leading zeros).
    
    good_multisets = set()
    
    half_len = (n + 1) // 2
    start = 10**(half_len - 1)
    end = 10**half_len
    
    for i in range(start, end):
        s = str(i)
        # Construct palindrome
        if n % 2 == 0:
            res = s + s[::-1]
        else:
            res = s + s[:-1][::-1]
        
        val = int(res)
        if val % k == 0:
            # This is a k-palindromic integer.
            # Its multiset of digits is "good".
            digits = sorted([int(d) for d in res])
            good_multisets.add(tuple(digits))
            
    total_count = 0
    for ms in good_multisets:
        # Count unique n-digit integers from multiset ms
        def count_permutations(multiset):
            if not multiset: return 1
            total = math.factorial(len(multiset))
            counts = Counter(multiset)
            for char in counts:
                total //= math.factorial(counts[char])
            return total
        
        # Total permutations
        total_perms = count_permutations(ms)
        
        # Subtract permutations with leading zero
        if 0 in ms:
            remaining_ms = list(ms)
            remaining_ms.remove(0)
            count_with_leading_zero = count_permutations(tuple(remaining_ms))
            total_perms -= count_with_leading_zero
            
        total_count += total_perms
        
    return total_count
