def split_csv(line):
    """
    Takes one line of comma-separated text and gives back its fields 
    in order as a list of strings. Handles blank lines by returning an empty list.
    """
    if not line or line == "\n":
        return []
    
    # Remove trailing newline if present
    line = line.rstrip('\r\n')
    
    # If the line is completely empty after stripping, return empty list
    if not line:
        return []

    return line.split(',')
