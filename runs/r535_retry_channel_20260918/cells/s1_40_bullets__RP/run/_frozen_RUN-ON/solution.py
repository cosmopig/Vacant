def format_list(strings):
    if not strings:
        return ""
    return "\n".join([f"- {s}" for s in strings])

# Example usage (not required by task but good for testing)
if __name__ == "__main__":
    test_input = ["apple", "banana", "cherry"]
    print(format_list(test_input))
