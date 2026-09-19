def find_longest_common_prefix(words):
    if not words:
        return ""
    
    # Start with the first word as the initial prefix
    prefix = words[0]
    
    for i in range(1, len(words)):
        current_word = words[i]
        # Shorten the prefix until it matches the start of current_word
        while not current_word.startswith(prefix):
            prefix = prefix[:-1]
            if not prefix:
                break
    
    return prefix

def main():
    import sys
    # The task doesn't specify input format, but usually it's space-separated or newline-separated words.
    # Since the prompt says "Given a list of words", I'll assume they are provided as arguments 
    # or from standard input. Let's check if there's any convention.
    # Usually for these types of tasks, reading all remaining stdin is safe.
    input_data = sys.stdin.read().split()
    if not input_data:
        print("")
        return

    result = find_longest_common_prefix(input_data)
    print(result)

if __name__ == "__main__":
    main()
