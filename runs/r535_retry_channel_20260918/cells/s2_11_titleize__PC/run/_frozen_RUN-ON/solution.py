def titleize(s):
    words = s.split(' ')
    result = []
    for word in words:
        if word.isupper():
            result.append(word)
        else:
            result.append(word.capitalize())
    return ' '.join(result)

# Examples to test (optional, but good for verification)
if __name__ == "__main__":
    print(titleize("hello world"))          # Hello World
    print(titleize("NASA is cool"))        # NASA Is Cool
    print(titleize("the FBI agent"))       # The FBI Agent
    print(titleize("i love python"))       # I Love Python
