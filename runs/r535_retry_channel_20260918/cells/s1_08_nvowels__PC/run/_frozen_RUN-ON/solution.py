def n_vowels(s: str) -> int:
    """
    Count the vowels in a piece of text.
    The five English vowel letters count, in either case. Every other character
    does not, and that includes the letter y.

    Args:
        s (str): The input string to count vowels from.

    Returns:
        int: The number of vowels found in the string.
    """
    vowels = "aeiouAEIOU"
    count = 0
    for char in s:
        if char in vowels:
            count += 1
    return count
