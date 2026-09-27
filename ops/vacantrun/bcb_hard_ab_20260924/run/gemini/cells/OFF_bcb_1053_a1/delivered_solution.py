import pandas as pd
from sklearn.feature_extraction.text import CountVectorizer
import matplotlib.pyplot as plt

# Constants
STOP_WORDS = ["a", "an", "the", "in", "on", "at", "and", "or"]

def task_func(file_path, save_path=None):
    try:
        # 1. Read CSV
        try:
            df = pd.read_csv(file_path)
        except FileNotFoundError:
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # 2. Identify text data
        if 'Text' in df.columns:
            text_data = df['Text']
        else:
            df = pd.read_csv(file_path, header=None)
            text_data = df.iloc[:, 0]
            
        text_data = text_data.dropna().astype(str)
        
        if text_data.empty:
            return None
            
        # 3. Count words
        vectorizer = CountVectorizer(stop_words=STOP_WORDS)
        X = vectorizer.fit_transform(text_data)
        counts = X.sum(axis=0).A1
        words = vectorizer.get_feature_names_out()
        
        # 4. Get top 10
        word_counts = pd.Series(counts, index=words)
        top_10 = word_counts.sort_values(ascending=False).head(10)
        
        # 5. Plot
        fig, ax = plt.subplots()
        top_10.plot(kind='bar', ax=ax)
        ax.set_title('Top 10 most common words')
        ax.set_xlabel('Words')
        ax.set_ylabel('Frequency')
        
        if save_path:
            plt.savefig(save_path)
            plt.close(fig)
            return None
        else:
            return ax

    except FileNotFoundError:
        # Re-raise FileNotFoundError to let it propagate
        raise
    except Exception as e:
        # For any other errors, print the error and return None
        print(e)
        return None
