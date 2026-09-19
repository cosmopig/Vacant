def format_seconds(total_seconds):
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours}:{minutes:02d}:{seconds:02d}"

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        print(format_seconds(int(sys.argv[1])))
