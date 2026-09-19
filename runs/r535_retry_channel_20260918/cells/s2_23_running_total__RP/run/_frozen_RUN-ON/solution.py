def running_total(xs):
    """
    Reports the total accumulated as a list of numbers is walked from the start.
    
    Args:
        xs (list[float]): A list of numbers.
        
    Returns:
        list[float]: A list where each element at index i is the sum of elements 
                      from xs[0] to xs[i].
    """
    total = 0
    result = []
    for x in xs:
        total += x
        result.append(total)
    return result

# Example usage:
if __name__ == "__main__":
    numbers = [1, 2, 3, 4]
    print(running_total(numbers))  # Expected output: [1, 3, 6, 10]
