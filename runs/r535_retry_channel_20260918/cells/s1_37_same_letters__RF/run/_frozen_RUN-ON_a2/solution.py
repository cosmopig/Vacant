def solution(s1, s2):
    # Normalize both strings: lowercase and remove spaces
    s1_clean = "".join(c.lower() for c in s1 if c != " ")
    s2_clean = "".join(c.lower() for c in s2 if c != " ")
    
    # Check if they have the same characters with the same frequencies
    return sorted(s1_clean) == sorted(s2_clean)

if __name__ == "__main__":
    import sys
    # The task doesn't specify input format, but usually it's two lines or space-separated.
    # Since I need to provide a solution that can be tested, 
    # I'll assume the standard way of reading from stdin if needed, 
    # but for now, let's just define the function as requested.
    pass
