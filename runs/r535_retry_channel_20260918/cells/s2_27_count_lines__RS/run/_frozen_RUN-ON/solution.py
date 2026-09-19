def count_lines(text):
    if not text:
        return 0
    return len(text.splitlines())

# Example usage (optional, but good for testing)
if __name__ == "__main__":
    test_text = "line1\nline2\nline3"
    print(f"Lines in '{test_text}': {count_lines(test_text)}")
    
    empty_text = ""
    print(f"Lines in empty string: {count_lines(empty_text)}")

    no_newline_text = "line1\nline2"
    print(f"Lines in '{no_newline_text}': {count_lines(no_newline_text)}")
