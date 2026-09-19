def caesar(s, k):
    out = []
    for c in s.lower():
        if "a" <= c <= "z":
            out.append(chr((ord(c) - 97 + k) % 26 + 97))
        else:
            out.append(c)
    return "".join(out)
