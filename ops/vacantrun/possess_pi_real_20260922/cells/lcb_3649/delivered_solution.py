from typing import List
import itertools

def findMinimumTime(strength: List[int], K: int) -> int:
    n = len(strength)
    min_time = float('inf')
    
    # Since n is small (up to 8), we can iterate through all permutations of the locks.
    for p in itertools.permutations(range(n)):
        current_time = 0
        current_X = 1
        for i in p:
            # Time needed to break lock with strength[i] given current factor X
            # Energy at time delta_t is delta_t * X. We need delta_t * X >= strength[i].
            # So delta_t = ceil(strength[i] / X)
            delta_t = (strength[i] + current_X - 1) // current_X
            current_time += delta_t
            current_X += K
        
        if current_time < min_time:
            min_time = current_time
            
    return int(min_time)
