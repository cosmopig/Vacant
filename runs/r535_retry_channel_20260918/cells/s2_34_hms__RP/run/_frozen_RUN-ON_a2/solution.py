def hms(seconds):
    # The difference between two timestamps that are not guaranteed to be in order
    # means we should take the absolute value.
    if seconds < 0:
        raise ValueError("Seconds must be non-negative")
    
    seconds = int(seconds)
    
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    
    if hours == 0:
        return f"{minutes:02d}:{secs:02d}"
    else:
        return f"{hours}:{minutes:02d}:{secs:02d}"
