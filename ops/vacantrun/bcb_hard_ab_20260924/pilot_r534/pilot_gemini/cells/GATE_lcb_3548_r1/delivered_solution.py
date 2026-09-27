import math

def countGoodIntegers(n: int, k: int):
    def get_digit_counts(num_str):
        counts = [0] * 10
        for char in num_str:
            counts[int(char)] += 1
        return tuple(counts)

    good_multisets = set()
    
    m = (n + 1) // 2
    
    for first_half in range(10**(m-1), 10**m):
        s = str(first_half)
        if n % 2 == 0:
            full_s = s + s[::-1]
        else:
            full_s = s + s[:-1][::-1]
        
        num = int(full_s)
        if num % k == 0:
            good_multisets.add(get_digit_counts(full_s))
            
    total_good_integers = 0
    fact = [math.factorial(i) for i in range(n + 1)]
    
    for counts in good_multisets:
        denom = 1
        for c in counts:
            denom *= fact[c]
        
        perms = fact[n] // denom
        
        if counts[0] > 0:
            denom_leading_zero = 1
            denom_leading_zero *= fact[counts[0] - 1]
            for i in range(1, 10):
                denom_leading_zero *= fact[counts[i]]
            perms_leading_zero = fact[n-1] // denom_leading_zero
            perms -= perms_leading_zero
            
        total_good_integers += perms
        
    return total_good_integers
