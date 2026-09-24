import unicodedata
import csv
from collections import Counter
import matplotlib.pyplot as plt

def task_func(csv_file):
    words = []
    try:
        with open(csv_file, mode='r', encoding='utf-8') as f:
            reader = csv.reader(f)
            for row in reader:
                for cell in row:
                    # Normalize to ASCII
                    normalized_text = unicodedata.normalize('NFKD', cell).encode('ascii', 'ignore').decode('ascii')
                    # Simple word tokenization (split by whitespace)
                    words.extend(normalized_text.split())
    except FileNotFoundError:
        raise FileNotFoundError(f"The CSV file cannot be found at the specified path: {csv_file}")
    except IOError as e:
        raise IOError(f"An error occurred while reading the file: {e}")

    counts = Counter(words)
    most_common = counts.most_common(10)

    if not most_common:
        fig, ax = plt.subplots()
        return ax, []

    words_list, counts_list = zip(*most_common)

    fig, ax = plt.subplots()
    ax.bar(words_list, counts_list)
    ax.set_xlabel('Words')
    ax.set_ylabel('Frequency')
    ax.set_title('10 Most Common Words')

    return ax, most_common
