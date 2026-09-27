import re
import nltk
from string import punctuation
def task_func(df):
    if 'Title' not in df.columns or 'Content' not in df.columns:
        raise ValueError("DataFrame is missing required columns.")

    # Filter articles whose titles contain "like" or "what" (case-insensitive)
    mask = df['Title'].astype(str).str.contains('like|what', case=False, na=False)
    filtered_df = df[mask]

    word_counts = {}
    for content in filtered_df['Content']:
        content_str = str(content)
        # Remove punctuation marks
        clean_content = content_str.translate(str.maketrans('', '', punctuation))
        # Tokenize into words (alphanumeric sequences)
        words = re.findall(r'\w+', clean_content)
        for word in words:
            word_counts[word] = word_counts.get(word, 0) + 1

    return word_counts
