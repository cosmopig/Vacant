def split_csv(line):
    """
    Takes one line of comma-separated text and gives back its fields 
    in order as a list of strings.
    """
    # The prompt says "The lines come straight off a file that sometimes has a blank line in it."
    # If the line is completely empty (just \n), split_csv should return an empty list or handle it correctly.
    # A truly blank line might be just "\n". rstrip('\r\n') makes it "".
    
    stripped = line.rstrip('\r\n')
    if not stripped:
        return []
    
    return stripped.split(',')
