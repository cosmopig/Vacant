import heapq
from typing import List

def minTimeToReach(moveTime: List[List[int]]) -> int:
    n = len(moveTime)
    m = len(moveTime[0])
    
    # dist[i][j] will store the minimum time to reach room (i, j)
    dist = [[float('inf')] * m for _ in range(n)]
    dist[0][0] = 0
    
    # Priority queue stores (time, r, c)
    pq = [(0, 0, 0)]
    
    while pq:
        d, r, c = heapq.heappop(pq)
        
        if d > dist[r][c]:
            continue
        
        if r == n - 1 and c == m - 1:
            return int(d)
        
        for dr, dc in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            nr, nc = r + dr, c + dc
            if 0 <= nr < n and 0 <= nc < m:
                new_dist = max(d, moveTime[nr][nc]) + 1
                if new_dist < dist[nr][nc]:
                    dist[nr][nc] = new_dist
                    heapq.heappush(pq, (new_dist, nr, nc))
    
    return int(dist[n-1][m-1])
