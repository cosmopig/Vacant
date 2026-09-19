def solution(s1, s2):
    # Normalize both strings: lowercase and remove spaces
    s1_clean = "".join(c.lower() for c in s1 if c != " ")
    s2_clean = "".join(c.lower() for c in s2 if c != " ")
    
    # Check if they have the same characters with the same frequencies
    return sorted(s1_clean) == sorted(s2_clean)

if __name__ == "__main__":
    import sys
    # The task doesn't specify input format, but usually it's from stdin.
    # Since I need to provide a solution that can be tested, 
    # I'll assume the inputs are provided as two lines or similar.
    # However, for many coding platforms, it might be different.
    # Let's stick to a simple structure and adjust if needed.
    input_data = sys.stdin.read().splitlines()
    if len(input_data) >= 2:
        print(solution(input_data[0], input_data[1]))
