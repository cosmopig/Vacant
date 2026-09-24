import urllib.request
import re
from collections import Counter
import matplotlib.pyplot as plt

def task_func(url):
    # Download the text file from the URL
    with urllib.request.urlopen(url) as response:
        content = response.read().decode('utf-8')

    # Use a basic regular expression to find words (case-sensitive, as per goal.md)
    words = re.findall(r'\w+', content)

    # Count the frequency of each word
    word_counts = Counter(words)

    # Get the ten most common words
    most_common = word_counts.most_common(10)

    # Plot a bar chart showing the ten most frequently occurring words
    fig, ax = plt.subplots()
    labels, values = zip(*most_common) if most_common else ([], [])
    ax.bar(labels, values)
    ax.set_xlabel('Words')
    ax.set_ylabel('Frequency')
    ax.set_title('Ten Most Frequent Words')

    return word_counts, ax
