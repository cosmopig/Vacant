import numpy as np
import matplotlib.pyplot as plt
import re
from collections import Counter

def task_func(mystrings, text):
    if not text:
        raise ValueError("If the input text is empty.")
    
    # All operations are case-insensitive
    text_lower = text.lower()
    
    protected_regions = []
    for s in mystrings:
        s_lower = s.lower()
        if not s_lower: continue
        start = 0
        while True:
            idx = text_lower.find(s_lower, start)
            if idx == -1:
                break
            protected_regions.append((idx, idx + len(s_lower)))
            start = idx + 1
    
    # Sort and merge protected regions
    protected_regions.sort()
    merged = []
    if protected_regions:
        curr_start, curr_end = protected_regions[0]
        for i in range(1, len(protected_regions)):
            next_start, next_end = protected_regions[i]
            if next_start < curr_end:
                curr_end = max(curr_end, next_end)
            else:
                merged.append((curr_start, curr_end))
                curr_start, curr_end = next_start, next_end
        merged.append((curr_start, curr_end))
    
    # Now split the text by whitespace, but only if it's not inside a protected region
    words = []
    current_word_start = 0
    i = 0
    while i < len(text):
        if text[i].isspace():
            # Check if this space is inside any merged protected region
            is_protected = False
            for start, end in merged:
                if start <= i < end:
                    is_protected = True
                    break
            
            if not is_protected:
                # Split here
                word = text[current_word_start:i]
                if word.strip():
                    words.append(word.strip().lower().replace(' ', '_'))
                current_word_start = i + 1
        i += 1
    
    # Add the last word
    last_word = text[current_word_start:]
    if last_word.strip():
        words.append(last_word.strip().lower().replace(' ', '_'))

    # If no words were found but text was not empty, it might be one word with spaces
    if not words and text:
        words = [text.lower().replace(' ', '_')]

    # Count frequencies while preserving order
    counts = Counter()
    order = []
    for w in words:
        if w not in counts:
            order.append(w)
            counts[w] = 1
        else:
            counts[w] += 1
            
    # Plotting
    plt.figure()
    plt.bar(order, [counts[w] for w in order])
    return plt.gca()
