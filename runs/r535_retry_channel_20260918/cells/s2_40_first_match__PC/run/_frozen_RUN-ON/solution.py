from typing import List, Optional

def first_match(words: List[str], prefix: str) -> Optional[str]:
    """
    Finds the first word in the list that starts with the given prefix,
    ignoring case. Returns None if no match is found.
    """
    prefix_lower = prefix.lower()
    for word in words:
        if word.lower().startswith(prefix_lower):
            return word
    return None
