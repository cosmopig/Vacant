def tidy_text(text):
    # Remove leading and trailing whitespace, then replace multiple whitespaces with one space
    return " ".join(text.split())

if __name__ == "__main__":
    import sys
    # Read from stdin or use a default if no input is provided
    input_text = sys.stdin.read()
    print(tidy_text(input_text))
