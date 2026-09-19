from typing import List, Tuple

def merge_intervals(intervals: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
    if not intervals:
        return []

    # Sort the intervals by their start points
    sorted_intervals = sorted(intervals, key=lambda x: x[0])

    merged = []
    current_start, current_end = sorted_intervals[0]

    for i in range(1, len(sorted_intervals)):
        next_start, next_end = sorted_intervals[i]
        
        # If the next interval overlaps or touches the current one
        if next_start <= current_end:
            current_end = max(current_end, next_end)
        else:
            merged.append((current_start, current_end))
            current_start, current_end = next_start, next_end

    merged.append((current_start, current_end))
    return merged

if __name__ == "__main__":
    # Example usage:
    test_cases = [
        ([(1, 3), (2, 6), (8, 10), (15, 18)], [(1, 6), (8, 10), (15, 18)]),
        ([(1, 4), (4, 5)], [(1, 5)]),
        ([(1, 3), (5, 7)], [(1, 3), (5, 7)]),
        ([], []),
    ]

    for intervals, expected in test_cases:
        result = merge_intervals(intervals)
        assert result == expected, f"Failed for {intervals}: expected {expected}, got {result}"
    print("All tests passed!")
