def find_longest_stretch(text):
    if not text:
        return None

    max_char = ""
    max_length = 0
    current_char = ""
    current_length = 0

    for char in text:
        if char == current_char:
            current_length += 1
        else:
            if current_length > max_length:
                max_length = current_length
                max_char = current_char
            current_char = char
            current_length = 1

    # Final check for the last stretch
    if current_length > max_length:
        max_length = current_length
        max_char = current_char

    return {
        "character": max_char,
        "length": max_length
    }

if __name__ == "__main__":
    import sys
    input_text = sys.stdin.read().strip()
    if input_text:
        result = find_longest_stretch(input_text)
        print(result)
