from typing import List
import heapq


def resultsArray(queries: List[List[int]], k: int) -> List[int]:
    # Max-heap of the k smallest distances, stored as negative values.
    heap = []
    results = []

    for x, y in queries:
        d = abs(x) + abs(y)

        if len(heap) < k:
            heapq.heappush(heap, -d)
        elif d < -heap[0]:
            # Replace the current largest distance among the k smallest.
            heapq.heapreplace(heap, -d)

        if len(heap) == k:
            results.append(-heap[0])
        else:
            results.append(-1)

    return results
