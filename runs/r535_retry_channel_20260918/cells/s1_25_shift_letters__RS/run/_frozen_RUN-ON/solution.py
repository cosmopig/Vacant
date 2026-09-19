def shift_letters(text, shift):
    result = []
    for char in text:
        if char.isalpha():
            # Determine the base ASCII value (A=65, a=97)
            start = ord('A') if char.isupper() else ord('a')
            # Calculate the new position
            # (current_pos - start + shift) % 26 + start
            new_char = chr((ord(char) - start + shift) % 26 + start)
            result.append(new_char)
        else:
            result.append(char)
    return "".join(result)

if __name__ == "__main__":
    import sys
    # Example usage: python solution.py "Hello, World!" 3
    # Output should be: "Khoor, Zruog!"
    if len(sys.argv) > 2:
        text = sys.argv[1]
        try:
            shift_val = int(sys.argv[2])
            print(shift_letters(text, shift_val))
        except ValueError:
            pass
