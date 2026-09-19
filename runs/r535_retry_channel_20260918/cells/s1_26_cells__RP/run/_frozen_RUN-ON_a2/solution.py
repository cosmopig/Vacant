def cells(line):
    # Remove trailing newline
    line = line.rstrip('\r\n')
    
    # Split by comma
    fields = line.split(',')
    
    # Strip spaces from each field and return them as a list
    return [field.strip() for field in fields]

if __name__ == "__main__":
    import sys
    line = sys.stdin.readline()
    if line:
        for field in cells(line):
            print(field)
