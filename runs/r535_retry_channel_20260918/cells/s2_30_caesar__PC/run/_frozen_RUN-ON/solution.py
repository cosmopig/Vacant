def caesar(s, k):
    result = []
    for char in s:
        if char.isalpha():
            # Determine the base (ASCII value for 'A' or 'a')
            start = ord('A') if char.isupper() else ord('a')
            # Calculate the new character position
            # (current_pos - start + k) % 26 gives the new position in 0-25 range
            new_char = chr(start + (ord(char) - start + k) % 26)
            result.append(new_char)
        else:
            # Non-alphabetic characters are left as is
            result.append(char)
    return "".join(result)

if __name__ == "__main__":
    import sys
    if len(sys.argv) == 3:
        text = sys.argv[1]
        shift = int(sys.argv[2])
        print(caesar(text, shift))
