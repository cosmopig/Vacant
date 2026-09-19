def pairwise_diff(numbers):
    if len(numbers) < 2:
        return []
    
    steps = []
    for i in range(len(numbers) - 1):
        steps.append(numbers[i+1] - numbers[i])
    return steps

def solution(numbers):
    return pairwise_diff(numbers)
