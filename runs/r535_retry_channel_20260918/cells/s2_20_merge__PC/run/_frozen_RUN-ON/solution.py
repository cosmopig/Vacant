def merge(a, b):
    """
    Combines two lookups into one new lookup holding everything from both of them.
    Where both hold the same key, the value from the second one is kept.
    """
    # Start with a copy of the first dictionary to avoid mutating it
    result = dict(a)
    # Update with values from the second dictionary
    result.update(b)
    return result

# Examples/Tests:
if __name__ == "__main__":
    defaults = {"theme": "light", "font_size": 12, "show_sidebar": True}
    user_config = {"theme": "dark", "font_size": 14}
    
    merged = merge(defaults, user_config)
    print(f"Defaults: {defaults}")
    print(f"User Config: {user_config}")
    print(f"Merged: {merged}")
    # Expected Merged: {'theme': 'dark', 'font_size': 14, 'show_sidebar': True}
