from typing import List
import itertools

def findMinimumTime(strength: List[int], K: int) -> int:
    n = len(strength)
    min_time = float('inf')
    
    # Since n is small (up to 8), we can iterate through all permutations of the locks.
    for p in itertools.permutations(strength):
        current_x = 1
        total_time = 0
        for s in p:
            # The time taken to break a lock with strength s and current factor x is ceil(s/x).
            t = (s + current_x - 1) // current_x
            total_time += t
            current_x += K
        if total_time < min_time:
            min_time = total_time
            
    return int(min_time)
