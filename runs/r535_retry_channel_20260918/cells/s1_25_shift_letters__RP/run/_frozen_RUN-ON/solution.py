def shift_letters(text, shift):
    result = []
    for char in text:
        if 'a' <= char <= 'z':
            # Shift lowercase letters
            shifted_char = chr((ord(char) - ord('a') + shift) % 26 + ord('a'))
            result.append(shifted_char)
        elif 'A' <= char <= 'Z':
            # Shift uppercase letters
            shifted_char = chr((ord(char) - ord('A') + shift) % 26 + ord('A'))
            result.append(shifted_char)
        else:
            # Keep non-letter characters as they are
            result.append(char)
    return "".join(result)

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 2:
        text = sys.argv[1]
        try:
            shift = int(sys.argv[2])
            print(shift_letters(text, shift))
        except ValueError:
            pass
