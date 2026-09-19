def merge(a, b):
    """
    Combines two lookups into one new lookup holding everything from both of them.
    The first (a) is the set of defaults, and the second (b) is what the user 
    put in their own configuration file. If a key exists in both, the value 
    from b takes precedence.
    """
    # Start with all items from the default lookup
    result = a.copy()
    # Update with items from the user's lookup (overwriting defaults)
    result.update(b)
    return result

# Example usage:
if __name__ == "__main__":
    defaults = {"theme": "light", "font_size": 12, "show_sidebar": True}
    user_config = {"theme": "dark", "font_size": 14}
    
    merged = merge(defaults, user_config)
    print(merged)  # Expected: {'theme': 'dark', 'font_size': 14, 'show_sidebar': True}
