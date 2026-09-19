def split_csv(line):
    """
    Takes one line of comma-separated text and gives back its fields 
    in order as a list of strings. Handles blank lines by returning an empty list.
    """
    # Strip trailing newline if present
    line = line.rstrip('\n')
    
    if not line:
        return []
    
    return [field.strip() for field in line.split(',')]
