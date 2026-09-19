def tidy_text(text):
    # Remove leading and trailing whitespace, then replace multiple whitespaces with one space
    return " ".join(text.split())

if __name__ == "__main__":
    import sys
    input_text = sys.stdin.read()
    print(tidy_text(input_text))
