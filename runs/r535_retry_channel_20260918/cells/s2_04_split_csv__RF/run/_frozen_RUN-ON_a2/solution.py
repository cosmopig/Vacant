def split_csv(line):
    """
    Takes one line of comma-separated text and gives back its fields 
    in order as a list of strings.
    
    There are no quoted fields and no escaped commas, so every comma separates.
    The lines come straight off a file that sometimes has a blank line in it.
    """
    # Remove trailing newline if present
    line = line.rstrip('\n\r')
    
    if not line:
        return []

    return line.split(',')
