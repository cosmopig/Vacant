def solution(numbers):
    if len(numbers) < 2:
        return []
    
    steps = []
    for i in range(len(numbers) - 1):
        diff = numbers[i+1] - numbers[i]
        steps.append(diff)
    return steps

# Example usage (optional, but good for testing if needed)
if __name__ == "__main__":
    import sys
    # This part is just to allow running the script with input if desired
    # But the task says "Write the code in a file called solution.py"
    pass
