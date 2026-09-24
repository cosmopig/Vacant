import re
import nltk
from string import punctuation
def task_func(df):
    if df.empty:
        raise ValueError("DataFrame is empty")
    if 'Title' not in df.columns or 'Content' not in df.columns:
        raise ValueError("Missing columns")

    # Filter articles whose titles contain "like" or "what" (case-insensitive)
    mask = df['Title'].str.contains('like|what', case=False, na=False)
    filtered_df = df[mask]

    word_counts = {}
    for content in filtered_df['Content']:
        if isinstance(content, str):
            # Replace punctuation with space to treat it as a delimiter
            translator = str.maketrans(punctuation, ' ' * len(punctuation))
            clean_content = content.translate(translator)
            words = clean_content.split()
            for word in words:
                word_counts[word] = word_counts.get(word, 0) + 1
    
    return word_counts
