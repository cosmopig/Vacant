def same_letters(s1, s2):
    """
    Decide whether two pieces of text are made of exactly the same
    characters in some order, each used the same number of times.

    Upper and lower case are treated as the same, and spaces are ignored
    altogether. Everything else counts. The answer is a true or false value.
    """
    # Normalize both strings: lowercase and remove spaces
    s1_norm = [c.lower() for c in s1 if c != " "]
    s2_norm = [c.lower() for c in s2 if c != " "]
    
    # Check if they have the same characters with the same frequencies
    return sorted(s1_norm) == sorted(s2_norm)

if __name__ == "__main__":
    print(same_letters("Listen", "Silent"))  # True
    print(same_letters("Hello World", "world hello"))  # True
    print(same_letters("abc", "abd"))  # False
