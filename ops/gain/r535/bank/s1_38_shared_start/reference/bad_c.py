def common_prefix(words):
    out = ""
    for i in range(min(len(w) for w in words)):
        c = words[0][i]
        if all(w[i] == c for w in words):
            out += c
        else:
            break
    return out
