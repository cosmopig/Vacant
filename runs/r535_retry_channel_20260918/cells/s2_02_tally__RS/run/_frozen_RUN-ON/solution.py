import collections
import re

def tally(words):
    """
    Takes a list of words and returns a dictionary mapping each word 
    to its frequency, normalizing for common variations in manual typing.
    """
    # Define normalization rules (lowercase, remove punctuation)
    counts = collections.Counter()
    for word in words:
        # Basic normalization: lowercase and remove non-alphanumeric characters
        clean_word = re.sub(r'[^a-zA-Z0-9]', '', word).lower()
        if clean_word:
            counts[clean_word] += 1
    return dict(counts)
