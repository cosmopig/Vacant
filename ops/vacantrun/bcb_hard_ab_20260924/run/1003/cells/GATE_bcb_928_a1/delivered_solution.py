from collections import Counter
import itertools
import string
def task_func(word: str) -> dict:
    # Generate all possible two-letter combinations of lowercase English alphabets
    combinations = ["".join(p) for p in itertools.product(string.ascii_lowercase, repeat=2)]
    
    # Count the frequency of each two-letter substring in the word
    counts = Counter()
    for i in range(len(word) - 1):
        substring = word[i:i+2]
        if len(substring) == 2 and substring.islower():
            counts[substring] += 1
            
    # Create the result dictionary with all combinations as keys
    result = {}
    for combo in combinations:
        result[combo] = counts.get(combo, 0)
        
    return result
