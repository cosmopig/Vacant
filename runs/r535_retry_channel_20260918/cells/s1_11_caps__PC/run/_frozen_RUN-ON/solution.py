def caps(s: str) -> str:
    words = s.split(' ')
    result = []
    for word in words:
        if not word:
            result.append("")
            continue
        
        new_word = ""
        for i, char in enumerate(word):
            if i % 2 == 0:
                new_word += char.upper()
            else:
                new_word += char.lower()
        result.append(new_word)
    return " ".join(result)
