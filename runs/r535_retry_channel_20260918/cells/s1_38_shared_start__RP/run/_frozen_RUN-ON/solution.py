def find_longest_common_prefix(words):
    if not words:
        return ""
    
    # Start with the first word as the initial prefix
    prefix = words[0]
    
    for i in range(1, len(words)):
        # Shorten the prefix until it matches the start of words[i]
        while not words[i].startswith(prefix):
            prefix = prefix[:-1]
            if not prefix:
                return ""
                
    return prefix

def main():
    import sys
    input_data = sys.stdin.read().split()
    words = [w for w in input_data if w]
    
    if not words:
        print("")
    else:
        print(find_longest_common_prefix(words))

if __name__ == "__main__":
    main()

