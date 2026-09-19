def running_total(xs):
    """
    Reports the total accumulated as a list of numbers is walked from the start.
    Each entry includes the reading at that position.
    """
    running_total = []
    current_sum = 0
    for x in xs:
        current_sum += x
        running_total.append(current_sum)
    return running_total

# Example usage:
# print(running_total([1, 2, 3]))  # Expected output: [1, 3, 6]
