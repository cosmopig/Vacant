def find_longest_common_prefix(words):
    if not words:
        return ""
    
    # Start with the first word as the initial prefix
    prefix = words[0]
    
    for i in range(1, len(words)):
        current_word = words[i]
        # Shrink the prefix until it matches the start of current_word
        while not current_word.startswith(prefix):
            prefix = prefix[:-1]
            if not prefix:
                break
    
    return prefix

def main():
    import sys
    # The problem description doesn't specify input format, 
    # but usually it's words separated by whitespace or on new lines.
    # Let's assume words are provided as arguments or from stdin.
    # Since the task says "Given a list of words", I'll read all input.
    input_data = sys.stdin.read().split()
    if not input_data:
        print("")
        return

    result = find_longest_common_prefix(input_data)
    print(result)

if __name__ == "__main__":
    main()
