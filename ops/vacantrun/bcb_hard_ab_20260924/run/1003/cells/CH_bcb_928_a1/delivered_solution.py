from collections import Counter
import itertools
import string

def task_func(word: str) -> dict:
    # Generate all possible two-letter combinations of the lowercase English alphabets
    # These are "aa", "ab", ..., "zz"
    combinations = list(itertools.product(string.ascii_lowercase, repeat=2))
    
    # Initialize dictionary with 0 for all combinations
    result = {f"{a}{b}": 0 for a, b in combinations}
    
    # Count occurrences of each two-letter substring in the word
    if len(word) >= 2:
        counts = Counter()
        for i in range(len(word) - 1):
            substring = word[i:i+2]
            # Only count if it's a lowercase alphabet combination
            if len(substring) == 2 and substring.islower() and substring.isalpha():
                counts[substring] += 1
        
        for key, count in counts.items():
            result[key] = count
            
    return result
