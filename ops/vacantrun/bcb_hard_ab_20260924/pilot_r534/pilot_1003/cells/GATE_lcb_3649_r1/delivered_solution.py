from typing import List
import itertools

def findMinimumTime(strength: List[int], K: int) -> int:
    n = len(strength)
    min_time = float('inf')
    
    # Try all permutations of the locks to break.
    # Since n is small (up to 8), n! is at most 40320.
    for p in itertools.permutations(range(n)):
        current_X = 1
        total_time = 0
        for idx in p:
            target = strength[idx]
            # The energy starts at 0 after each lock is broken (or initially).
            # Every minute, the energy of the sword increases by current_X.
            # We need to find the minimum minutes m >= 1 such that m * current_X >= target.
            # Since target >= 1 and current_X >= 1, m = ceil(target / current_X).
            m = (target + current_X - 1) // current_X
            total_time += m
            # After breaking a lock, the energy of the sword resets to 0 and X increases by K.
            current_X += K
        
        if total_time < min_time:
            min_time = total_time
            
    return int(min_time)
