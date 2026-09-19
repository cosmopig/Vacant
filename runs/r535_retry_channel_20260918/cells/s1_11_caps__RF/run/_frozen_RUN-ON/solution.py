def transform(phrase):
    words = phrase.split(' ')
    transformed_words = []
    for word in words:
        if not word:
            transformed_words.append("")
            continue
        
        new_word = ""
        for i, char in enumerate(word):
            if i % 2 == 0:
                new_word += char.upper()
            else:
                new_word += char.lower()
        transformed_words.append(new_word)
    return " ".join(transformed_words)

if __name__ == "__main__":
    import sys
    input_data = sys.stdin.read()
    if input_data:
        print(transform(input_data), end='')
