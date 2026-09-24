import urllib.request
import re
from collections import Counter
import matplotlib.pyplot as plt

def task_func(url):
    # Download the text file from the specified URL
    with urllib.request.urlopen(url) as response:
        text = response.read().decode('utf-8')
    
    # Identify words using a basic regular expression (case-sensitive)
    words = re.findall(r'\w+', text)
    
    # Count the frequency of each word
    word_counts = Counter(words)
    
    # Get the ten most frequently occurring words
    most_common = word_counts.most_common(10)
    
    if not most_common:
        fig, ax = plt.subplots()
        ax.set_title("No words found")
        return word_counts, ax

    # Extract labels and counts for the bar chart
    labels, counts = zip(*most_common)
    
    # Plot the bar chart
    fig, ax = plt.subplots()
    ax.bar(labels, counts)
    ax.set_xlabel('Words')
    ax.set_ylabel('Frequency')
    ax.set_title('Ten Most Frequent Words')
    plt.xticks(rotation=45)
    plt.tight_layout()
    
    return word_counts, ax
