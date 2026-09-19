def hms(seconds):
    if seconds < 0:
        raise ValueError("Seconds must be non-negative")
    
    minutes, sec = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    
    if hours == 0:
        return f"{minutes:02d}:{sec:02d}"
    else:
        return f"{hours:02d}:{minutes:02d}:{sec:02d}"
