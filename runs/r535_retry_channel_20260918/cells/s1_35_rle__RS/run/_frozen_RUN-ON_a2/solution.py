from typing import List, Tuple

def compress(text: str) -> List[Tuple[str, int]]:
    if not text:
        return []
    
    result = []
    count = 1
    for i in range(1, len(text)):
        if text[i] == text[i-1]:
            count += 1
        else:
            result.append((text[i-1], count))
            count = 1
    result.append((text[-1], count))
    return result

# Example usage:
if __name__ == "__main__":
    test_cases = [
        ("aaabbbccc", [('a', 3), ('b', 3), ('c', 3)]),
        ("abc", [('a', 1), ('b', 1), ('c', 1)]),
        ("", []),
        ("aaaaa", [('a', 5)]),
        ("aabbbaaa", [('a', 2), ('b', 3), ('a', 3)])
    ]

    for text, expected in test_cases:
        actual = compress(text)
        print(f"Input: {text} | Expected: {expected} | Actual: {actual}")
        assert actual == expected
