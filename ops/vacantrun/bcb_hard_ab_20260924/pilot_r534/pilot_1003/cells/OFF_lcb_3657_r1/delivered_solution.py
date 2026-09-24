from typing import List

def merge_intervals(intervals):
    if not intervals:
        return []
    # Sort by start point
    intervals.sort()
    merged = []
    curr_start, curr_end = intervals[0]
    for i in range(1, len(intervals)):
        next_start, next_end = intervals[i]
        if next_start <= curr_end + 1:
            curr_end = max(curr_end, next_end)
        else:
            merged.append((curr_start, curr_end))
            curr_start, curr_end = next_start, next_end
    merged.append((curr_start, curr_end))
    return merged

def has_valid_cut(L, R, merged_intervals):
    if L > R:
        return False
    if not merged_intervals:
        return True
    
    m = len(merged_intervals)
    # Case 1: There is a valid cut k in [L, R] such that k < A_1
    if L < merged_intervals[0][0]:
        return True
    # Case 2: There is a valid cut k in [L, R] such that k > B_m
    if R > merged_intervals[-1][1]:
        return True
    # Case 3: There is a gap between some A_j and B_{j-1} that intersects [L, R]
    for j in range(m - 1):
        B_curr = merged_intervals[j][1]
        A_next = merged_intervals[j+1][0]
        if max(L, B_curr + 1) <= min(R, A_next - 1):
            return True
    return False

def checkValidCuts(n: int, rectangles: List[List[int]]) -> bool:
    # Horizontal cuts
    blocked_h = []
    for r in rectangles:
        y1, y2 = r[1], r[3]
        start = y1 + 1
        end = y2 - 1
        if start <= end:
            blocked_h.append((max(1, start), min(n - 1, end)))
    
    merged_h = merge_intervals(blocked_h)
    min_y2 = min(r[3] for r in rectangles)
    max_y1 = max(r[1] for r in rectangles)
    
    for r in rectangles:
        y1, y2 = r[1], r[3]
        L1, R1 = max(1, min_y2), min(n - 1, y1)
        L2, R2 = max(1, y2), min(n - 1, max_y1)
        if L1 <= R1 and L2 <= R2:
            if has_valid_cut(L1, R1, merged_h) and has_valid_cut(L2, R2, merged_h):
                return True

    # Vertical cuts
    blocked_v = []
    for r in rectangles:
        x1, x2 = r[0], r[2]
        start = x1 + 1
        end = x2 - 1
        if start <= end:
            blocked_v.append((max(1, start), min(n - 1, end)))
    
    merged_v = merge_intervals(blocked_v)
    min_x2 = min(r[2] for r in rectangles)
    max_x1 = max(r[0] for r in rectangles)
    
    for r in rectangles:
        x1, x2 = r[0], r[2]
        L1, R1 = max(1, min_x2), min(n - 1, x1)
        L2, R2 = max(1, x2), min(n - 1, max_x1)
        if L1 <= R1 and L2 <= R2:
            if has_valid_cut(L1, R1, merged_v) and has_valid_cut(L2, R2, merged_v):
                return True

    return False
