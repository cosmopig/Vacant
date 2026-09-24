import re
import nltk
from string import punctuation
def task_func(df):
    if df.empty or 'Title' not in df.columns or 'Content' not in df.columns:
        raise ValueError("DataFrame is empty or does not contain necessary columns.")

    # Filter articles whose titles contain "like" or "what" (case-insensitive)
    pattern = re.compile(r'like|what', re.IGNORECASE)
    filtered_df = df[df['Title'].str.contains(pattern, na=False)]

    word_counts = {}
    for content in filtered_df['Content']:
        # Remove punctuation and split into words
        content_no_punct = content.translate(str.maketrans('', '', punctuation))
        words = re.findall(r'\w+', content_no_punct)
        for word in words:
            word_counts[word] = word_counts.get(word, 0) + 1

    return word_counts
