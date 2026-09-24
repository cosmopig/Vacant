from typing import List
import itertools

def findMinimumTime(strength: List[int], K: int) -> int:
    n = len(strength)
    min_total_time = float('inf')
    
    # Since n is small (1 <= n <= 8), we can try all permutations of locks.
    for p in itertools.permutations(range(n)):
        current_time = 0
        current_x = 1
        
        for idx in p:
            target = strength[idx]
            # We need to find the minimum time t such that sum_{i=0}^{t-1} current_x >= target
            # The energy after t minutes is current_x * (1 + 2 + ... + (t-1)) if x was constant?
            # Wait, let's re-read.
            # "Every minute, the energy of the sword increases by the current factor X."
            # Initial energy = 0, initial X = 1.
            # Minute 1: Energy becomes 0 + X_initial = 1. (Wait, example says at time 1, energy is 1)
            # Let's re-examine Example 1: strength = [3,4,1], K = 1
            # Time 0: Energy 0, X 1
            # Time 1: Energy 1, X 1. Action: Break 3rd lock (strength[2]=1). Updated X = 1+1=2.
            # Time 2: Energy 2, X 2. Nothing.
            # Time 3: Energy 4, X 2. Action: Break 2nd lock (strength[1]=4). Updated X = 2+1=3.
            # Time 4: Energy 3? No, wait. "After breaking a lock, the energy of the sword resets to 0"
            # Let's re-trace Example 1 carefully.
            # strength = [3,4,1], K = 1
            # Lock order in example seems to be: 3rd (index 2), then 2nd (index 1), then 1st (index 0).
            # Wait, the explanation says "Break 3^rd Lock" at Time 1. strength[2] is 1.
            # At Time 1, Energy = 1. Since 1 >= strength[2], it breaks. X becomes 1+K = 2.
            # At Time 2: Energy was 0 (reset), increases by X=2. New energy = 2.
            # At Time 3: Energy was 2, increases by X=2. New energy = 4. Since 4 >= strength[1], it breaks. X becomes 2+K = 3.
            # At Time 4: Energy was 0 (reset), increases by X=3. New energy = 3. Since 3 >= strength[0], it breaks. X becomes 3+K = 4.
            # Total time = 4.
            
            # So for each lock in the permutation:
            # We need to find minimum t > 0 such that current_x * t >= target? No, because X is constant while breaking a single lock.
            # Wait, "Every minute, the energy of the sword increases by the current factor X."
            # If we start at time T with energy 0 and factor X:
            # At T+1, energy = X
            # At T+2, energy = X + X = 2X
            # At T+3, energy = 2X + X = 3X
            # ...
            # At T+t, energy = t * X.
            # We need t * X >= target => t = ceil(target / X).
            
            t = (target + current_x - 1) // current_x
            current_time += t
            current_x += K
            
        min_total_time = min(min_total_time, current_time)
        
    return int(min_total_time)

