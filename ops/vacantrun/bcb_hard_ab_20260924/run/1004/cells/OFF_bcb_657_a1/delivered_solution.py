import re
import nltk
from gensim.models import Word2Vec
# Constants
ALPHANUMERIC = re.compile(r'[\W_]+')
def task_func(texts, stopwords=None):
    if stopwords is None:
        stopwords = set()
    
    processed_texts = []
    for text in texts:
        # Remove non-alphanumeric characters except space
        text = ALPHANUMERIC.sub(' ', text)
        # Lowercase
        text = text.lower()
        # Tokenize and remove stopwords
        tokens = [word for word in text.split() if word not in stopwords]
        processed_texts.append(tokens)
    
    # Train Word2Vec model
    model = Word2Vec(sentences=processed_texts, vector_size=100, window=5, min_count=1, workers=4)
    return model
