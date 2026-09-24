import numpy as np
import matplotlib.pyplot as plt
import re
from collections import Counter

def task_func(mystrings, text):
    if not text:
        raise ValueError("If the input text is empty.")
    
    # All operations are case-insensitive.
    text_lower = text.lower()
    
    # Find all occurrences of each s in mystrings (case-insensitive) 
    # and replace their internal spaces with underscores.
    mask = [False] * len(text)
    
    sorted_mystrings = sorted(myststrings, key=len, reverse=True)
    for s in sorted_mystrings:
        s_lower = s.lower()
        start = 0
        while True:
            idx = text_lower.find(s_lower, start)
            if idx == -1:
                break
            # Found a match from idx to idx + len(s_lower)
            for i in range(idx, idx + len(s_lower)):
                mask[i] = True
            start = idx + 1
            
    result_chars = []
    for i in range(len(text)):
        if mask[i] and text[i] == ' ':
            result_chars.append('_')
        else:
            result_chars.append(text[i])
    
    final_text = "".join(result_chars)
    # The goal says "All operations are case-insensitive". 
    # This usually means we should lowercase the words before counting.
    words_to_plot = final_text.lower().split(' ')
    
    counts = Counter()
    unique_order = []
    for w in words_to_plot:
        if not w: continue # handle multiple spaces if any
        if w not in counts:
            unique_order.append(w)
            counts[w] = 1
        else:
            counts[w] += 1
            
    plt.figure()
    # The goal says "The frequency plot displays each unique word on the x-axis 
    # in the order they appear after modification with its corresponding frequency on the y-axis."
    plt.plot(unique_order, [counts[w] for w in unique_order])
    return plt.gca()
