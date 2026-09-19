def hms(seconds):
    # Ensure seconds is non-negative as it's a difference between timestamps
    seconds = abs(int(seconds))
    
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    
    return f"{hours:02}:{minutes:02}:{secs:02}"
