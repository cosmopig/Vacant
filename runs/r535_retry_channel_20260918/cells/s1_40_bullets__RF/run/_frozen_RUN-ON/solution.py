def format_list(strings):
    if not strings:
        return ""
    return "\n".join([f"- {s}" for s in strings])

# Example usage (not required by task but good for testing)
# print(format_list(["apple", "banana", "cherry"]))
