def solution(s1, s2):
    # Normalize both strings: lowercase and remove spaces
    s1_clean = "".join(c.lower() for c in s1 if c != " ")
    s2_clean = "".join(c.lower() for c in s2 if c != " ")
    
    # Check if they have the same characters with the same frequencies
    return sorted(s1_clean) == sorted(s2_clean)

# Example usage:
if __name__ == "__main__":
    print(solution("Listen", "Silent"))  # Expected: True
    print(solution("Hello World", "world hello"))  # Expected: True
    print(solution("abc", "abd"))  # Expected: False
