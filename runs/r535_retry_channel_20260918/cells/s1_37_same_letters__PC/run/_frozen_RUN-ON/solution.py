def same_letters(a: str, b: str) -> bool:
    # Normalize both strings: lowercase and remove spaces
    a_norm = a.lower().replace(" ", "")
    b_norm = b.lower().replace(" ", "")
    
    # Check if they have the same characters with the same frequencies
    return sorted(a_norm) == sorted(b_norm)
