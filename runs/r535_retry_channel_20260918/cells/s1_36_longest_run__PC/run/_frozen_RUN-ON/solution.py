def longest_run(s):
    if not s:
        return {"ch": "", "n": 0}

    max_char = ""
    max_len = -1
    
    current_char = ""
    current_len = 0
    
    for char in s:
        if char == current_char:
            current_len += 1
        else:
            if current_len > max_len:
                max_len = current_len
                max_char = current_char
            current_char = char
            current_len = 1
            
    # Final check for the last run
    if current_len > max_len:
        max_len = current_len
        max_char = current_char
        
    return {"ch": max_char, "n": max_len}

if __name__ == "__main__":
    # Test cases
    print(longest_run("aaabbbbbc")) # Expected: {'ch': 'b', 'n': 5}
    print(longest_run("aabbbbbaaaa")) # Expected: {'ch': 'b', 'n': 5}
    print(longest_run("aaabbb")) # Expected: {'ch': 'a', 'n': 3} (earlier one)
    print(longest_run("abcde")) # Expected: {'ch': 'a', 'n': 1}
