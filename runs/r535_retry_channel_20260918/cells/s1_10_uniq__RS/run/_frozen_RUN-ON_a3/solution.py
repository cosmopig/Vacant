def remove_repeats(items):
    seen = set()
    result = []
    for item in items:
        if item not in seen:
            result.append(item)
            seen.add(item)
    return result

# Example usage:
if __name__ == "__main__":
    input_list = [1, 2, 3, 2, 4, 1, 5]
    print(remove_repeats(input_list))  # Expected output: [1, 2, 3, 4, 5]
