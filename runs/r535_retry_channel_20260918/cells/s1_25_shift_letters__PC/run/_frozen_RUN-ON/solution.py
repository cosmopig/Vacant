def shift_letters(s: str, k: int) -> str:
    result = []
    for char in s:
        if 'a' <= char <= 'z':
            # Shift lowercase letters
            shifted = chr((ord(char) - ord('a') + k) % 26 + ord('a'))
            result.append(shifted)
        elif 'A' <= char <= 'Z':
            # Shift uppercase letters
            shifted = chr((ord(char) - ord('A') + k) % 26 + ord('A'))
            result.append(shifted)
        else:
            # Keep non-letter characters as they are
            result.append(char)
    return "".join(result)

if __name__ == "__main__":
    # Examples
    print(shift_letters("abc", 1))      # Expected: "bcd"
    print(shift_letters("xyz", 3))      # Expected: "abc"
    print(shift_letters("Hello, World!", 5)) # Expected: "Mjqqt, Btwqi!"
    print(shift_letters("abc", -1))     # Expected: "zab"
    print(shift_letters("abc", 27))     # Expected: "bcd"
