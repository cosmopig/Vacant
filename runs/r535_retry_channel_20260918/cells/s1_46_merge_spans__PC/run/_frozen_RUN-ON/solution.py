def merge_spans(spans):
    if not spans:
        return []

    # Sort the intervals by their start points
    sorted_spans = sorted(spans, key=lambda x: x[0])

    merged = []
    current_span = list(sorted_spans[0])

    for i in range(1, len(sorted_spans)):
        next_span = sorted_spans[i]
        # If the next span starts before or at the end of the current span, merge them.
        if next_span[0] <= current_span[1]:
            current_span[1] = max(current_span[1], next_span[1])
        else:
            merged.append(current_span)
            current_span = list(next_span)

    merged.append(current_span)
    return merged

if __name__ == "__main__":
    # Test cases
    print(merge_spans([[1, 3], [2, 6], [8, 10], [15, 18]]))  # Expected: [[1, 6], [8, 10], [15, 18]]
    print(merge_spans([[1, 4], [4, 5]]))                    # Expected: [[1, 5]]
    print(merge_spans([[1, 10], [2, 3], [4, 5], [6, 7]]))   # Expected: [[1, 10]]
    print(merge_spans([[1, 2], [3, 4]]))                    # Expected: [[1, 2], [3, 4]]
