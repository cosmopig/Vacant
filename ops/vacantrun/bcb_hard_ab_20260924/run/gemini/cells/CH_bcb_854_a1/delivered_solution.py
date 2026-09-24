from functools import reduce
from itertools import permutations
import math

def task_func(numbers):
    if not isinstance(numbers, list):
        raise TypeError("numbers must be a list")
    for n in numbers:
        if not isinstance(n, int):
            raise TypeError("numbers must be a list of integers")
        if n < 0:
            raise ValueError("numbers must be non-negative")
    
    if not numbers:
        return [], []
    
    perms = list(permutations(numbers))
    fac_sums = [sum(math.factorial(x) for x in p) for p in perms]
    return fac_sums, perms
