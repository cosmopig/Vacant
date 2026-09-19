def solution(counts):
    if not counts:
        return None
    
    # Find the maximum count
    max_count = max(counts.values())
    
    # Filter names that have the maximum count
    candidates = [name for name, count in counts.items() if count == max_count]
    
    # Sort candidates alphabetically and return the first one
    return sorted(candidates)[0]

if __name__ == "__main__":
    import sys
    import json
    
    # Read input from stdin as a JSON object (dictionary)
    try:
        input_data = json.load(sys.stdin)
        print(solution(input_data))
    except EOFError:
        pass
    except Exception as e:
        pass
