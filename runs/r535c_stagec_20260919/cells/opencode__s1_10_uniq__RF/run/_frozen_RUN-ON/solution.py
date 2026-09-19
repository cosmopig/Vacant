def remove_repeats(input_list):
    seen = set()
    result = []
    for item in input_list:
        if item not in seen:
            result.append(item)
            seen.add(item)
    return result

# Example usage:
# print(remove_repeats([1, 2, 3, 1, 2]))  # Output: [1, 2, 3]
