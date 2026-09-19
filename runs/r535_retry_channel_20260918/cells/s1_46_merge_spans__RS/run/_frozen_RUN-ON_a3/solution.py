def merge_intervals(intervals):
    if not intervals:
        return []

    # Sort intervals by start time
    sorted_intervals = sorted(intervals, key=lambda x: x[0])
    
    merged = []
    for interval in sorted_intervals:
        # If the list of merged intervals is empty or if the current 
        # interval does not overlap with the previous one, simply append it.
        if not merged or interval[0] > merged[-1][1]:
            merged.append(list(interval))
        else:
            # Otherwise, there is an overlap, so merge the current 
            # interval with the previous one by updating the end time.
            merged[-1][1] = max(merged[-1][1], interval[1])
            
    return merged

def solve():
    import sys
    input_data = sys.stdin.read().split()
    if not input_data:
        return
    
    # The problem description doesn't specify the format of input, 
    # but usually it's a sequence of pairs.
    # Let's assume the input is a series of integers representing start and end points.
    intervals = []
    for i in range(0, len(input_data), 2):
        if i + 1 < len(input_data):
            intervals.append([int(input_data[i]), int(input_data[i+1])])
            
    result = merge_intervals(intervals)
    for interval in result:
        print(f"{interval[0]} {interval[1]}")

if __name__ == "__main__":
    solve()
