from typing import List
import itertools

def findMinimumTime(strength: List[int], K: int) -> int:
    n = len(strength)
    min_time = float('inf')
    
    # Try all permutations of the locks to break.
    # Since n is small (up to 8), there are at most 8! = 40320 permutations.
    for p in itertools.permutations(range(n)):
        current_time = 0
        current_energy = 0
        current_X = 1
        
        for i in p:
            s = strength[i]
            # Calculate how many minutes are needed to reach the required strength s.
            # At each minute, energy increases by current_X.
            if current_energy < s:
                m = (s - current_energy + current_X - 1) // current_X
                current_time += m
                current_energy += m * current_X
            
            # Break the lock: energy resets to 0 and factor X increases by K.
            current_energy = 0
            current_X += K
        
        if current_time < min_time:
            min_time = current_time
            
    return int(min_time)
