def camelise(identifier):
    words = identifier.split('_')
    # The first word remains lowercase, subsequent words are capitalized.
    return words[0] + ''.join(word.capitalize() for word in words[1:])

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        print(camelise(sys.argv[1]))
