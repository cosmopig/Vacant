def initials(full_name):
    parts = full_name.split()
    return [part[0].upper() for part in parts if part]

if __name__ == "__main__":
    import sys
    # The test runner seems to import 'initials' from 'solution', 
    # so we just need the function defined at the top level.
    pass

