def solution(value, lower_edge, upper_edge):
    if lower_edge <= value <= upper_edge:
        return value
    elif value < lower_edge:
        return lower_edge
    else:
        return upper_edge

# Examples (optional for verification)
if __name__ == "__main__":
    print(solution(5, 0, 10))   # Expected: 5
    print(solution(-2, 0, 10))  # Expected: 0
    print(solution(12, 0, 10))  # Expected: 10
