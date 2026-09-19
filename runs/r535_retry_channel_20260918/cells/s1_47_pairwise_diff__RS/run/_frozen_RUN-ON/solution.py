def solution(numbers):
    if len(numbers) < 2:
        return []
    
    steps = []
    for i in range(len(numbers) - 1):
        steps.append(numbers[i+1] - numbers[i])
    return steps

# Example usage (optional, but good for testing if needed)
if __name__ == "__main__":
    print(solution([1, 3, 6]))  # Expected: [2, 3]
    print(solution([10, 5, 0])) # Expected: [-5, -5]
    print(solution([1]))         # Expected: []
