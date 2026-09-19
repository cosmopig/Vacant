def solution(phrase):
    words = phrase.split(' ')
    result = []
    for word in words:
        if not word:
            result.append("")
        else:
            # The prompt says "first letter of every word in upper case and 
            # every other letter of that word in lower case."
            # This means the first character is uppercase, and all subsequent characters are lowercase.
            new_word = word[0].upper() + word[1:].lower()
            result.append(new_word)
    return ' '.join(result)

if __name__ == "__main__":
    import sys
    # Read from stdin to handle potential multi-line input or just a single line
    input_data = sys.stdin.read()
    if input_data:
        print(solution(input_data))
