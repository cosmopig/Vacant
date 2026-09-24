import math
from collections import Counter

def countGoodIntegers(n: int, k: int) -> int:
    def get_multiset(num_str):
        counts = [0] * 10
        for char in num_str:
            counts[int(char)] += 1
        return tuple(counts)

    def count_permutations(counts, n):
        # Total permutations
        total = math.factorial(n)
        for c in counts:
            if c > 0:
                total //= math.factorial(c)
        
        # Permutations starting with 0
        if counts[0] > 0:
            starting_with_zero = math.factorial(n - 1)
            # Decrement counts[0] for the calculation
            counts_copy = list(counts)
            counts_copy[0] -= 1
            for c in counts_copy:
                if c > 0:
                    starting_with_zero //= math.factorial(c)
            return total - starting_with_zero
        else:
            return total

    unique_multisets = set()
    
    # Generate n-digit palindromes
    m = (n + 1) // 2
    start = 10**(m - 1)
    end = 10**m
    
    for i in range(start, end):
        s = str(i)
        if n % 2 == 0:
            p_str = s + s[::-1]
        else:
            p_str = s + s[:-1][::-1]
        
        p_int = int(p_str)
        if p_int % k == 0:
            unique_multisets.add(get_multiset(p_str))
            
    total_good_integers = 0
    for ms in unique_multisets:
        total_good_integers += count_permutations(ms, n)
        
    return total_good_integers

if __name__ == "__main__":
    print(f"Test 1 (n=3, k=5): {countGoodIntegers(3, 5)} (Expected: 27)")
    print(f"Test 2 (n=1, k=4): {countGoodIntegers(1, 4)} (Expected: 2)")
    print(f"Test 3 (n=5, k=6): {countGoodIntegers(5, 6)} (Expected: 2468)")
