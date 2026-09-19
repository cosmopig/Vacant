def snakeify(s: str) -> str:
    if not s:
        return ""
    
    result = []
    # The first character is always included as lowercase, 
    # unless it's a capital that starts the word (which we handle by just lowercasing).
    # Actually, the rule says "Every capital after the first character starts a new word".
    
    for i, char in enumerate(s):
        if i > 0 and char.isupper():
            result.append('_')
            result.append(char.lower())
        else:
            result.append(char.lower())
            
    return "".join(result)

# Examples:
# snakeify("SnakeCase") -> "snake_case"
# snakeify("camelCase") -> "camel_case"
# snakeify("SimpleHTTPRequest") -> "simple_h_t_t_p_request"
# snakeify("Already_snake") -> "already_snake"
