def title_case(s):
    return " ".join(w[:1].upper() + w[1:].lower() for w in s.split(" "))
