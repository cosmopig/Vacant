def format_time(seconds):
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    return f"{hours}:{minutes:02d}:{secs:02d}"

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        print(format_time(int(sys.argv[1])))
