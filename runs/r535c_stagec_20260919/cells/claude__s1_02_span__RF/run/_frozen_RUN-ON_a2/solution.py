def get_min_max(numbers):
    """
    Given a list of numbers, report the smallest and largest values
    together in one dictionary.
    """
    return {
        "smallest": min(numbers),
        "largest": max(numbers)
    }

if __name__ == "__main__":
    # Example usage:
    nums = [3, 1, 4, 2]
    print(get_min_max(nums))
