def shared_start(words):
    if not words:
        return ""
    
    # Start with the first word as the initial common prefix
    prefix = words[0]
    
    for i in range(1, len(words)):
        # Shrink the prefix until it matches the start of the current word
        while not words[i].startswith(prefix):
            prefix = prefix[:-1]
            if not prefix:
                return ""
                
    return prefix

# Example usage (optional for testing)
if __name__ == "__main__":
    print(f"'{shared_start(['flower', 'flow', 'flight'])}'")  # Expected: 'fl'
    print(f"'{shared_start(['dog', 'racecar', 'car'])}'")      # Expected: ''
    print(f"'{shared_start(['interspecies', 'interstellar', 'interstate'])}'") # Expected: 'inters'
