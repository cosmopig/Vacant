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
                    normalized_text = unicodedata.normalize('NFKD', cell).encode('ascii', 'ignore').decode('ascii')
                    # Split into words and filter out non-alphanumeric if needed, 
                    # but the goal just says "counts the words". Usually means split by whitespace.
                    words.extend(normalized_text.split())
            
            word_counts = Counter(words)
            most_common = word_counts.most_common(10)
            
            if not most_common:
                fig, ax = plt.subplots()
                return ax, []

            words_list = [item[0] for item in most_common]
            counts_list = [item[1] for item in most_common]
            
            fig, ax = plt.subplots()
            ax.bar(words_list, counts_list)
            ax.set_ylabel('Frequency')
            ax.set_title('Top 10 Most Common Words')
            plt.xticks(rotation=45)
            plt.tight_layout()
            
            return ax, most_common

    except FileNotFoundError:
        raise FileNotFoundError(f"The CSV file cannot be found at the specified path: {csv_file}")
    except IOError as e:
        raise IOError(f"An error occurred while reading the file: {e}")
