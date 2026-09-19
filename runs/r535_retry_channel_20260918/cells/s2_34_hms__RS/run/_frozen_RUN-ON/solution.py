def hms(seconds):
    # The problem states seconds is the difference between two timestamps 
    # that are not guaranteed to be in order, so it could be negative.
    # However, a clock-style label for duration should represent absolute time.
    seconds = abs(int(seconds))
    
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"
