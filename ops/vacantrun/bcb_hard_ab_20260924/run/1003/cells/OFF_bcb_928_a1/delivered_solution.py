from collections import Counter
import itertools
import string
def task_func(word: str) -> dict:
    # Generate all possible two-letter combinations of lowercase English alphabets as strings
    combinations = ["".join(comb) for comb in itertools.product(string.ascii_lowercase, repeat=2)]
    res = {comb: 0 for comb in combinations}
    
    # Count occurrences of each two-letter combination as a substring in the word
    for i in range(len(word) - 1):
        substring = word[i:i+2]
        if substring in res:
            res[substring] += 1
            
    return res
