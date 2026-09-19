from typing import List

def maxSum(grid: List[List[int]], limits: List[int], k: int) -> int:
    """
    Finds the maximum sum of at most k elements from a 2D matrix grid such that
    the number of elements taken from the i-th row does not exceed limits[i].
    """
    # For each row, we want to pick the largest possible values.
    # Since we can take up to 'limits[i]' elements from row 'i',
    # and we want to maximize the total sum of at most 'k' elements overall,
    # we should consider all positive elements in each row.
    # However, since grid[i][j] >= 0, we just take the largest ones.

    # To efficiently find the best k elements across rows with limits:
    # This is a variation of the knapsack problem or a greedy approach with constraints.
    # Because each row's choice is independent except for the total sum 'k',
    # and we want to maximize the sum, we can treat this as picking from
    # a pool of available elements.

    # For each row i, sort its elements in descending order.
    # Then, take at most limits[i] largest elements from that row.
    # Collect all these "best" candidates into a single list.
    candidates = []
    for i in range(len(grid)):
        row_elements = sorted(grid[i], reverse=True)
        # We can take at most limits[i] elements from this row.
        # Since grid values are non-negative, we only care about the top limits[i].
        num_to_take = min(len(row_elements), limits[i])
        candidates.extend(row_elements[:num_to_take])

    # Now we have a pool of candidates where each candidate represents
    # one of the best possible choices from its respective row,
    # respecting that row's limit.
    # To get the maximum sum of at most k elements, sort all candidates
    # descending and take the top k (or fewer if there are fewer than k).
    candidates.sort(reverse=True)

    return sum(candidates[:k])

