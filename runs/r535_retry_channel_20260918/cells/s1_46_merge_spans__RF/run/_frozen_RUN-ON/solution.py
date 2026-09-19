from typing import List

def merge_intervals(intervals: List[List[int]]) -> List[List[int]]:
    if not intervals:
        return []

    # Sort the intervals by their start points
    sorted_intervals = sorted(intervals, key=lambda x: x[0])
    
    merged = []
    for interval in sorted_intervals:
        # If merged is empty or current interval does not overlap with the last one
        if not merged or interval[0] > merged[-1][1]:
            merged.append(list(interval))
        else:
            # There is an overlap, so merge the current interval with the last one
            merged[-1][1] = max(merged[-1][1], interval[1])
            
    return merged

if __name__ == "__main__":
    # Example usage:
    test_cases = [
        [[1, 3], [2, 6], [8, 10], [15, 18]],
        [[1, 4], [4, 5]],
        [[1, 10], [2, 3], [4, 5], [6, 7], [8, 9], [10, 11]],
        [[1, 5], [2, 3]],
    ]

    for case in test_cases:
        print(f"Input: {case} -> Output: {merge_intervals(case)}")
