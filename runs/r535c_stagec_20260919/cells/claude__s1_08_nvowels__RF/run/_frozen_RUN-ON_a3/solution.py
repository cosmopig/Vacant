def count_vowels(text):
    vowels = "aeiouAEIOU"
    return sum(1 for char in text if char in vowels)

if __name__ == "__main__":
    import sys
    input_text = sys.stdin.read()
    print(count_vowels(input_text))
