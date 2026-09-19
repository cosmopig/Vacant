def count_vowels(text):
    vowels = "aeiouAEIOU"
    count = 0
    for char in text:
        if char in vowels:
            count += 1
    return count

if __name__ == "__main__":
    import sys
    input_text = sys.stdin.read() if not sys.stdin.isatty() else ""
    print(count_vowels(input_text))
