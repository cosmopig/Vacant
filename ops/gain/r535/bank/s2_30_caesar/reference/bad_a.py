def caesar(s, k):
    return "".join(chr((ord(c) + k) % 128) for c in s)
