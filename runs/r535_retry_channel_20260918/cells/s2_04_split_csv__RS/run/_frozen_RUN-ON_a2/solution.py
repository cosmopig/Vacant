def split_csv(line):
    """
    Takes one line of comma-separated text and gives back its fields 
    in order as a list of strings. Handles blank lines by returning an empty list.
    """
    # If the line is just whitespace or empty, return an empty list
    if not line.strip():
        return []
    
    # Strip trailing newline if present, then split by comma
    line = line.rstrip('\r\n')
    return line.split(',')
