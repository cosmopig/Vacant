from collections import Counter
import os
import json

def task_func(filename, directory):
    word_counts = Counter()
    total_words = 0
    
    if not os.path.isdir(directory):
        return 0

    for entry in os.listdir(directory):
        if entry.endswith('.txt'):
            file_path = os.path.join(directory, entry)
            if os.path.isfile(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        words = content.split()
                        word_counts.update(words)
                        total_words += len(words)
                except (IOError, OSError):
                    pass
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(dict(word_counts), f)
        
    return total_words
