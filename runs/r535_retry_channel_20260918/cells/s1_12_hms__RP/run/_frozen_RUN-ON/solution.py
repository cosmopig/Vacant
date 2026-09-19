def format_time(seconds):
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60
    return f"{hours}:{minutes:02d}:{seconds:02d}"

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        try:
            s = int(sys.argv[1])
            print(format_time(s))
        except ValueError:
            pass
