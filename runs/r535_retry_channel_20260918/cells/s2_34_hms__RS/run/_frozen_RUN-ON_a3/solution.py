def hms(seconds):
    # Ensure seconds is non-negative as it's a difference between timestamps
    seconds = abs(int(seconds))
    
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"
