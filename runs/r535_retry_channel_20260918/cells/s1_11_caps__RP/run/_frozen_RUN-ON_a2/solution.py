def caps(phrase):
    words = phrase.split(' ')
    result = []
    for word in words:
        if not word:
            result.append("")
        else:
            # First letter upper, rest lower
            new_word = ""
            for i, char in enumerate(word):
                if i == 0:
                    new_word += char.upper()
                else:
                    new_word += char.lower()
            result.append(new_word)
    return " ".join(result)

if __name__ == "__main__":
    import sys
    input_phrase = sys.stdin.read().strip()
    if input_phrase:
        print(caps(input_phrase))
