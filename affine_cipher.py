import math

def encode(plain_text, a, b):
    m = 26
    if math.gcd(a, m) != 1:
        raise ValueError("a and m must be coprime.")

    # Remove punctuation (anything not alpha, digit, or space)
    # And remove spaces from the input string based on analysis of test_encode_all_the_letters
    filtered = []
    for char in plain_text:
        if char.isalnum(): # Keep letters and digits
            filtered.append(char)
    
    # Encrypt letters, keep digits as is
    encrypted = []
    for char in filtered:
        if char.isalpha():
            if char.isupper():
                x = ord(char) - ord('A')
                res = (a * x + b) % m
                encrypted.append(chr(res + ord('A')))
            else:
                x = ord(char) - ord('a')
                res = (a * x + b) % m
                encrypted.append(chr(res + ord('a')))
        else:
            encrypted.append(char)
    
    # Group the resulting characters into chunks of 5, separated by a space
    result = ""
    for i in range(0, len(encrypted), 5):
        chunk = "".join(encrypted[i:i+5])
        result += chunk
        if i + 5 < len(encrypted):
            result += " "
    return result

def decode(ciphered_text, a, b):
    m = 26
    if math.gcd(a, m) != 1:
        raise ValueError("a and m must be coprime.")

    # Remove spaces (the output of encode has spaces every 5 chars)
    # And remove punctuation (though it shouldn't be there if encode was used correctly)
    filtered = []
    for char in ciphered_text:
        if char.isalnum(): # Keep letters and digits
            filtered.append(char)
    
    mmi = pow(a, -1, m)
    decoded = []
    for char in filtered:
        if char.isalpha():
            if char.isupper():
                y = ord(char) - ord('A')
                x = (mmi * (y - b)) % m
                decoded.append(chr(x + ord('A')))
            else:
                y = ord(char) - ord('a')
                x = (mmi * (y - b)) % m
                decoded.append(chr(x + ord('a')))
        else:
            decoded.append(char)
    
    return "".join(decoded)
