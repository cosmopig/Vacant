def camel_case(identifier):
    words = identifier.split('_')
    if not words:
        return ""
    
    # The first word remains lowercase
    first_word = words[0].lower()
    
    # Subsequent words start with a capital and continue in lowercase
    other_words = [word.capitalize() for word in words[1:]]
    
    return first_word + "".join(other_words)

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        print(camel_case(sys.argv[1]))
