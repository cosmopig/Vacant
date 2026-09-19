def solution(numbers):
    if len(numbers) < 2:
        return []
    
    steps = []
    for i in range(len(numbers) - 1):
        steps.append(numbers[i+1] - numbers[i])
    return steps

# Example usage (optional, for testing):
if __name__ == "__main__":
    print(solution([1, 3, 6, 10]))  # Expected: [2, 3, 4]
    print(solution([5, 5, 5]))       # Expected: [0, 0]
    print(solution([10]))             # Expected: []
    print(solution([]))               # Expected: []
