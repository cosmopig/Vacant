import itertools
from math import factorial

def countGoodIntegers(n: int, k: int) -> int:
    # Generate all multisets of digits {c0, ..., c9} such that sum(ci) = n
    all_multisets = []
    def generate(idx, current_counts, remaining):
        if idx == 10:
            if remaining == 0:
                all_multisets.append(list(current_counts))
            return
        for c in range(remaining + 1):
            current_counts[idx] = c
            generate(idx + 1, current_counts, remaining - c)

    generate(0, [0]*10, n)
    
    total_good_count = 0
    for counts in all_multisets:
        # Check if multiset can form a palindrome
        odd_counts = [i for i, c in enumerate(counts) if c % 2 != 0]
        if n % 2 == 0:
            if len(odd_counts) != 0: continue
        else:
            if len(odd_counts) != 1: continue
        
        mid = odd_counts[0] if n % 2 != 0 else -1
        half_counts = [c // 2 for c in counts]
        m = n // 2
        
        # Check if any palindrome is good
        is_good_multiset = False
        
        # Generate unique permutations of half_counts
        half_digits = []
        for i in range(10):
            half_digits.extend([i] * half_counts[i])
        
        unique_perms = set(itertools.permutations(half_digits))
        
        for p in unique_perms:
            if n % 2 == 0:
                val = 0
                for i in range(m):
                    val += p[i] * (10**(n - 1 - i) + 10**i)
            else:
                val = 0
                for i in range(m):
                    val += p[i] * (10**(n - 1 - i) + 10**i)
                val += mid * (10**m)
            
            # Check leading zero and divisibility by k
            if n == 1:
                first_digit = mid
            else:
                first_digit = p[0]
            
            if first_digit != 0 and val % k == 0:
                is_good_multiset = True
                break
        
        if is_good_multiset:
            # Count unique n-digit integers from this multiset
            total_perms = factorial(n)
            for c in counts:
                total_perms //= factorial(c)
            
            leading_zeros = 0
            if counts[0] > 0:
                leading_zeros = factorial(n - 1)
                leading_zeros //= factorial(counts[0] - 1)
                for i in range(1, 10):
                    leading_zeros //= factorial(counts[i])
            
            total_good_count += (total_perms - leading_zeros)
            
    return total_good_count
