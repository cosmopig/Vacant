def camel_case(identifier):
    words = identifier.split('_')
    # The first word remains lowercase, subsequent words start with a capital letter
    # followed by lowercase letters.
    return words[0] + ''.join(word.capitalize() for word in words[1:])

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        print(camel_case(sys.argv[1]))
