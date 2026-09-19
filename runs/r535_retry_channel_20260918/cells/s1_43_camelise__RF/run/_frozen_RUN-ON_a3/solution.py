def solution(identifier):
    words = identifier.split('_')
    if not words:
        return ""
    
    result = words[0].lower()
    for word in words[1:]:
        result += word.capitalize()
    
    return result

# Examples
if __name__ == "__main__":
    print(solution("hello_world"))       # Expected: HelloWorld
    print(solution("variable_name_one")) # Expected: VariableNameOne
    print(solution("simple_test"))       # Expected: SimpleTest
