from math import factorial
from itertools import combinations_with_replacement, permutations

def countGoodIntegers(n: int, k: int) -> int:
    def get_n_digit_count(n, counts):
        total = factorial(n)
        for c in counts:
            if c > 0:
                total //= factorial(c)
        if counts[0] > 0:
            return total * (n - counts[0]) // n
        return total

    total_good_integers = 0
    
    # combinations_with_replacement generates all possible multisets of n digits
    for combo in combinations_with_replacement(range(10), n):
        counts = [0] * 10
        for d in combo:
            counts[d] += 1
        
        # A multiset can form a palindrome if at most one digit has an odd count
        odd_counts = 0
        for c in counts:
            if c % 2 != 0:
                odd_counts += 1
        
        if (n % 2 == 0 and odd_counts == 0) or (n % 2 == 1 and odd_counts == 1):
            half_digits = []
            middle_digit = None
            for i in range(10):
                if counts[i] % 2 != 0:
                    middle_digit = i
                half_digits.extend([i] * (counts[i] // 2))
            
            is_good_multiset = False
            # Check all unique permutations of the first half of the palindrome
            for p in set(permutations(half_digits)):
                s_p = "".join(map(str, p))
                if n % 2 == 0:
                    palindrome_str = s_p + s_p[::-1]
                else:
                    palindrome_str = s_p + str(middle_digit) + s_p[::-1]
                
                # The rearranged palindrome must not have leading zeros
                if len(palindrome_str) > 1 and palindrome_str[0] == '0':
                    continue
                # For n=1, the only digit is middle_digit. 
                # If it's 0, it's not a valid 1-digit integer (though X=0 is not considered).
                if len(palindrome_str) == 1 and palindrome_str == '0':
                    continue
                
                if int(palindrome_str) % k == 0:
                    is_good_multiset = True
                    break
            
            if is_good_multiset:
                total_good_integers += get_n_digit_count(n, counts)
                
    return total_good_integers
