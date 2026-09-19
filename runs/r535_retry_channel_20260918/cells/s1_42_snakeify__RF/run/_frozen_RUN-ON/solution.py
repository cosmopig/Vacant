def snakeify(identifier):
    if not identifier:
        return ""
    
    result = []
    for i, char in enumerate(identifier):
        if char.isupper() and i > 0:
            result.append('_')
            result.append(char.lower())
        else:
            result.append(char.lower())
            
    return "".join(result)
