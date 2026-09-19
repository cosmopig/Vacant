def snakeify(identifier):
    if not identifier:
        return ""
    
    result = []
    # The first character is always included as lowercase, 
    # unless it's a capital that starts the word (which we handle by just lowercasing).
    # Actually, the rule says "Every capital after the first character starts a new word".
    
    for i, char in enumerate(identifier):
        if i > 0 and char.isupper():
            result.append('_')
            result.append(char.lower())
        else:
            result.append(char.lower())
            
    return "".join(result)

# Examples to test (not required by task but good for verification)
if __name__ == "__main__":
    print(snakeify("SnakeCase"))      # snake_case
    print(snakeify("camelCase"))      # camel_case
    print(snakeify("Simple"))         # simple
    print(snakeify("HTTPRequest"))    # h_t_t_p_request (based on "no special treatment for runs of capitals")
    print(snakeify("aCapital"))       # a_capital
    print(snakeify("ABC"))            # a_b_c
