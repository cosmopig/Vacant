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

if __name__ == "__main__":
    import sys
    import json

    # Read input from stdin as a list of lists (e.g., [[1, 3], [2, 6], [8, 10]])
    try:
        input_data = json.loads(sys.stdin.read())
        result = merge_intervals(input_data)
        print(json.dumps(result))
    except EOFError:
        pass
    except Exception as e:
        # In case of invalid input, just print nothing or handle accordingly
        pass

