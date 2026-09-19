def hms(seconds):
    # The difference between two timestamps that are not guaranteed to be in order
    # means we should take the absolute value.
    seconds = abs(int(seconds))
    
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"
