import pandas as pd
from sklearn.feature_extraction.text import CountVectorizer
import matplotlib.pyplot as plt
# Constants
STOP_WORDS = ["a", "an", "the", "in", "on", "at", "and", "or"]
def task_func(file_path, save_path=None):
    try:
        # Try reading with header
        try:
            df = pd.read_csv(file_path)
            if 'Text' in df.columns:
                text_series = df['Text']
            else:
                # If 'Text' is not there, it might be because there's no header.
                df = pd.read_csv(file_path, header=None)
                text_series = df.iloc[:, 0]
        except FileNotFoundError:
            raise FileNotFoundError(f"The file {file_path} was not found.")
        except Exception:
            # If reading with header failed for other reasons, try reading without header
            df = pd.read_csv(file_path, header=None)
            text_series = df.iloc[:, 0]

        # Convert to string and handle NaN
        text_data = text_series.astype(str).fillna('')
        
        # Vectorization
        vectorizer = CountVectorizer(stop_words=STOP_WORDS)
        X = vectorizer.fit_transform(text_data)
        
        # Word counts
        word_counts = X.sum(axis=0).A1
        words = vectorizer.get_feature_names_out()
        
        # Top 10
        word_counts_series = pd.Series(word_counts, index=words)
        top_10 = word_counts_series.sort_values(ascending=False).head(10)
        
        # Plotting
        fig, ax = plt.subplots()
        top_10.plot(kind='bar', ax=ax)
        
        if save_path:
            plt.savefig(save_path)
            plt.close(fig)
            return None
        else:
            return ax
            
    except FileNotFoundError as e:
        raise e
    except Exception as e:
        print(e)
        return None
