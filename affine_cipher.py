import math

class AffineCipher:
    def __init__(self, a, b):
        self.a = a
        self.b = b
        self.m = 26
        if math.gcd(a, self.m) != 1:
            raise ValueError("a and m must be coprime.")

    def encrypt(self, plain_text):
        # Remove punctuation (anything not alpha, digit, or space)
        filtered = []
        for char in plain_text:
            if char.isalnum(): # Keep letters and digits
                filtered.append(char)
        
        encrypted = []
        for char in filtered:
            if char.isalpha():
                if char.isupper():
                    x = ord(char) - ord('A')
                    res = (self.a * x + self.b) % self.m
                    encrypted.append(chr(res + ord('A')))
                else:
                    x = ord(char) - ord('a')
                    res = (self.a * x + self.b) % self.m
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

    def decrypt(self, ciphered_text):
        # Remove spaces (the output of encode has spaces every 5 chars)
        filtered = []
        for char in ciphered_text:
            if char.isalnum(): # Keep letters and digits
                filtered.append(char)
        
        mmi = pow(self.a, -1, self.m)
        decoded = []
        for char in filtered:
            if char.isalpha():
                if char.isupper():
                    y = ord(char) - ord('A')
                    x = (mmi * (y - self.b)) % self.m
                    decoded.append(chr(x + ord('A')))
                else:
                    y = ord(char) - ord('a')
                    x = (mmi * (y - self.b)) % self.m
                    decoded.append(chr(x + ord('a')))
            else:
                decoded.append(char)
        
        return "".join(decoded)

def encode(plain_text, a, b):
    cipher = AffineCipher(a, b)
    return cipher.encrypt(plain_text)

def decode(ciphered_text, a, b):
    cipher = AffineCipher(a, b)
    return cipher.decrypt(ciphered_text)
