import pandas as pd
import re
from sklearn.feature_extraction.text import CountVectorizer
# Constants
STOPWORDS = ['i', 'me', 'my', 'myself', 'we', 'our', 'ours', 'ourselves', 'you', 'your', 'yours', 'yourself',
             'yourselves', 'he', 'him', 'his', 'himself', 'she', 'her', 'hers', 'herself', 'it', 'its', 'itself',
             'they', 'them', 'their', 'theirs', 'themselves', 'what', 'which', 'who', 'whom', 'this', 'that', 'these',
             'those', 'am', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'having', 'do',
             'does', 'did', 'doing', 'a', 'an', 'the', 'and', 'but', 'if', 'or', 'because', 'as', 'until', 'while',
             'of', 'at', 'by', 'for', 'with', 'about', 'against', 'between', 'into', 'through', 'during', 'before',
             'after', 'above', 'below', 'to', 'from', 'up', 'down', 'in', 'out', 'on', 'off', 'over', 'under', 'again',
             'further', 'then', 'once']

def task_func(dataframe, text_column):
    # Preprocessing function to remove stopwords, numbers, and punctuation
    def preprocess_text(text):
        if not isinstance(text, str):
            return ""
        # Remove non-alphabetic characters (punctuation and numbers)
        text = re.sub(r'[^a-zA-Z\s]', '', text)
        # Tokenize into words and convert to lowercase
        words = text.lower().split()
        # Filter out stopwords
        filtered_words = [word for word in words if word not in STOPWORDS]
        return " ".join(filtered_words)

    # Apply preprocessing to the specified column
    dataframe[text_column] = dataframe[text_column].apply(preprocess_text)

    # Initialize CountVectorizer with the provided stopwords
    vectorizer = CountVectorizer(tokenizer=lambda x: x.split() if x else [], 
                                 token_pattern=None, 
                                 stop_words=STOPWORDS)
    
    # Fit and transform the text data
    # Note: The goal says "each word (after preprocessing) as a column and their count as rows"
    # This usually means a DataFrame where each row is an instance and columns are words.
    # However, CountVectorizer.fit_transform returns a sparse matrix of counts.
    # Let's check the exact wording: "Returns a DataFrame with each word (after preprocessing) as a column and their count as rows."
    # This might mean one row per original entry? Or one row per unique word? 
    # Usually, it means words are columns and counts for each document are in rows.
    
    counts = vectorizer.fit_transform(dataframe[text_column])
    
    # Convert to DataFrame
    df_result = pd.DataFrame(counts.toarray(), columns=vectorizer.get_feature_names_out())
    
    return df_result
