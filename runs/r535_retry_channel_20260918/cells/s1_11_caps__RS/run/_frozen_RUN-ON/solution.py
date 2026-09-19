def solution(phrase):
    words = phrase.split(' ')
    result = []
    for word in words:
        if not word:
            result.append("")
        else:
            # First letter upper, rest lower
            result.append(word[0].upper() + word[1:].lower())
    return ' '.join(result)
