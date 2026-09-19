from typing import List, Tuple

def compress(text: str) -> List[Tuple[str, int]]:
    if not text:
        return []
    
    compressed = []
    count = 1
    
    for i in range(1, len(text)):
        if text[i] == text[i-1]:
            count += 1
        else:
            compressed.append((text[i-1], count))
            count = 1
            
    compressed.append((text[-1], count))
    return compressed

# Example usage:
if __name__ == "__main__":
    test_cases = [
        ("aaabbc", [('a', 3), ('b', 2), ('c', 1)]),
        ("abc", [('a', 1), ('b', 1), ('c', 1)]),
        ("", []),
        ("aaaaa", [('a', 5)]),
    ]
    
    for text, expected in test_cases:
        result = compress(text)
        print(f"Input: {text} | Expected: {expected} | Result: {result}")
        assert result == expected
