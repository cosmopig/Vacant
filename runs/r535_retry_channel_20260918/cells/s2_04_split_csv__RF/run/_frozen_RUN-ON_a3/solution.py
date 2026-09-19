def split_csv(line):
    """
    Takes one line of comma-separated text and gives back its fields 
    in order as a list of strings.
    """
    stripped_line = line.rstrip('\r\n')
    if not stripped_line:
        return []
    
    return stripped_line.split(',')
