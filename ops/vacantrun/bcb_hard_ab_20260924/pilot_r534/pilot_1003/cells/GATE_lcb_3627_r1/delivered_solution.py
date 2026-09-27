from typing import List
import heapq

def minTimeToReach(moveTime: List[List[int]]) -> int:
    n = len(moveTime)
    m = len(moveTime[0])
    
    # dist[r][c] will store the minimum time to reach room (r, c)
    dist = [[float('inf')] * m for _ in range(n)]
    dist[0][0] = 0
    
    # Priority queue stores (time, r, c)
    pq = [(0, 0, 0)]
    
    while pq:
        t, r, c = heapq.heappop(pq)
        
        if t > dist[r][c]:
            continue
        
        if r == n - 1 and c == m - 1:
            return int(t)
        
        for dr, dc in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            nr, nc = r + dr, c + dc
            
            if 0 <= nr < n and 0 <= nc < m:
                # The time we can start moving to room (nr, nc) is max(t, moveTime[nr][nc])
                # Moving takes 1 second.
                new_t = max(t, moveTime[nr][nc]) + 1
                if new_t < dist[nr][nc]:
                    dist[nr][nc] = new_t
                    heapq.heappush(pq, (new_t, nr, nc))
    
    return int(dist[n-1][m-1])
