def squeeze(text):
    """
    Tidy a piece of text so that every run of whitespace inside it
    becomes one single space, and so that there is no whitespace left at the start
    or at the end.
    """
    return " ".join(text.split())

if __name__ == "__main__":
    import sys
    input_text = sys.stdin.read()
    print(squeeze(input_text))
