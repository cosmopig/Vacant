def is_pal(s: str) -> bool:
    # Filter out characters that are not letters or digits
    filtered_chars = [char.lower() for char in s if char.isalnum()]
    
    # Check if the filtered list of characters reads the same forwards and backwards
    return filtered_chars == filtered_chars[::-1]
