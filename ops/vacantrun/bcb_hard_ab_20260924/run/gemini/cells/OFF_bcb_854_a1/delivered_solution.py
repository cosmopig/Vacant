from functools import reduce
from itertools import permutations
import math

def task_func(numbers):
    if not isinstance(numbers, list):
        raise TypeError("numbers must be a list")
    
    for x in numbers:
        if not isinstance(x, int):
            raise TypeError("numbers must be a list of integers")
        if x < 0:
            raise ValueError("numbers must be non-negative")

    if not numbers:
        return [], []

    perms = list(permutations(numbers))
    fac_sums = []
    for p in perms:
        s = sum(math.factorial(x) for x in p)
        fac_sums.append(s)
    
    return fac_sums, perms
