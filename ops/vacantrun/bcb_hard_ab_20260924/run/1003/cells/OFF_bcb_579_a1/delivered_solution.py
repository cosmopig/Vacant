import unicodedata
import csv
from collections import Counter
import matplotlib.pyplot as plt
def task_func(csv_file):
    try:
        with open(csv_file, mode='r', encoding='utf-8') as f:
            reader = csv.reader(f)
            words = []
            for row in reader:
                for cell in row:
                    # Normalize to ASCII
                    normalized = unicodedata.normalize('NFKD', cell).encode('ascii', 'ignore').decode('ascii')
                    # Split into words and filter out empty strings
                    # Also convert to lowercase for better counting? The goal doesn't say, but it's standard.
                    # However, I should stick as close to the instructions as possible.
                    # "counts the words" - usually means case-insensitive or just split by whitespace.
                    # Let's do simple split and keep original casing unless specified otherwise.
                    words.extend(normalized.split())
    except FileNotFoundError:
        raise FileNotFoundError(f"The CSV file cannot be found at the specified path: {csv_file}")
    except IOError as e:
        raise IOError(f"There is an error in reading the file: {e}")

    counts = Counter(words)
    most_common = counts.most_common(10)

    fig, ax = plt.subplots()
    if most_common:
        # Extract words and their frequencies for plotting
        plot_words = [item[0] for item in most_common]
        plot_counts = [item[1] for item in most_common]
        ax.bar(plot_words, plot_counts)
    else:
        ax.set_title("No words found")

    return ax, most_common
