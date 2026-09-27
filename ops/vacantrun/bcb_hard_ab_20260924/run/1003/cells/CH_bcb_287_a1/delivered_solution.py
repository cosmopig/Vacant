from collections import Counter
import os
import json

def task_func(filename, directory):
    counts = {}
    total_words = 0
    
    if not os.path.isdir(directory):
        return 0
        
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.txt'):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        words = content.split()
                        count = len(words)
                        counts[file] = count
                        total_words += count
                except Exception:
                    pass
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(counts, f)
        
    return total_words
