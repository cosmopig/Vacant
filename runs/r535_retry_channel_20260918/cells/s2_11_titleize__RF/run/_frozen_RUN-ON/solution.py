def titleize(s):
    """
    Capitalizes the first letter of each word in a string, 
    where words are separated by single spaces.
    """
    if not s:
        return ""
    
    words = s.split(' ')
    titleized_words = [word.capitalize() for word in words]
    return ' '.join(titleized_words)

# Examples of usage:
# print(titleize("hello world"))  # Output: "Hello World"
# print(titleize("the quick brown fox"))  # Output: "The Quick Brown Fox"
