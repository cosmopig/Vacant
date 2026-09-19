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

# Examples
if __name__ == "__main__":
    print(f"'{titleize('hello world')}'")  # Expected: 'Hello World'
    print(f"'{titleize('the quick brown fox')}'")  # Expected: 'The Quick Brown Fox'
    print(f"'{titleize('i love coding')}'")  # Expected: 'I Love Coding'
    print(f"'{titleize('python is fun')}'")  # Expected: 'Python Is Fun'
