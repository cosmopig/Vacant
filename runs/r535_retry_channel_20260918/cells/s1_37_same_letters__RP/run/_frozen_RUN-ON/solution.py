def solution(s1, s2):
    # Normalize both strings: lowercase and remove spaces
    s1_norm = "".join(c.lower() for c in s1 if c != " ")
    s2_norm = "".join(c.lower() for c in s2 if c != " ")
    
    # Check if they have the same characters with the same frequencies
    return sorted(s1_norm) == sorted(s2_norm)

# Example usage:
if __name__ == "__main__":
    print(solution("Listen", "Silent"))  # True
    print(solution("Hello World", "world hello"))  # True
    print(solution("abc", "abd"))  # False
