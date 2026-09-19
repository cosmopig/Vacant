def count_lines(text):
    if not text:
        return 0
    return len(text.splitlines())

# Example usage (optional, but good for testing)
if __name__ == "__main__":
    test_text = "line1\nline2\nline3"
    print(count_lines(test_text))  # Should be 3
    
    test_text_no_trailing = "line1\nline2\nline3\n"
    print(count_lines(test_text_no_trailing))  # Should also be 3
