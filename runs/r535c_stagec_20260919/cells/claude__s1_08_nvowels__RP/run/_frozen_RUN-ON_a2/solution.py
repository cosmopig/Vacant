def n_vowels(text: str) -> int:
    """Count the vowels in a piece of text."""
    vowels = "aeiouAEIOU"
    count = 0
    for char in text:
        if char in vowels:
            count += 1
    return count
