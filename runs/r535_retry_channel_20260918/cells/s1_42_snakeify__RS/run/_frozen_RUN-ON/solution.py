def snakeify(identifier):
    if not identifier:
        return ""
    
    result = []
    # The first character is always included as lowercase, 
    # unless it's a capital that starts the word (which we handle by just lowercasing)
    # Actually, the rule says "Every capital after the first character starts a new word"
    # and "the result never starts with an underscore".
    
    for i, char in enumerate(identifier):
        if char.isupper() and i > 0:
            result.append('_')
            result.append(char.lower())
        else:
            result.append(char.lower())
            
    return "".join(result)

# Examples:
# "SnakeCase" -> "snake_case"
# "camelCase" -> "camel_case"
# "Simple" -> "simple"
# "ABC" -> "a_b_c" (Every capital after the first starts a new word)
# "MyID" -> "my_i_d"

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        print(snakeify(sys.argv[1]))
