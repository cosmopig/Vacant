def solution(numbers):
    if not numbers:
        return 0.0
    average = sum(numbers) / len(numbers)
    return round(average, 2)

# Example usage (not required by the task but good for testing):
# print(solution([1, 2, 3])) # Expected: 2.0
# print(solution([1, 2]))     # Expected: 1.5
