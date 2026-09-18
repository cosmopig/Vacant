def title_case(s):
    out = []
    for w in s.split(" "):
        if w.isupper():
            out.append(w)
        else:
            out.append(w[:1].upper() + w[1:].lower())
    return " ".join(out)
