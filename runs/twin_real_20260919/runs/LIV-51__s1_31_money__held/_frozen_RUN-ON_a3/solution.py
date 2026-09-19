def format_cents(cents):
    dollars = cents // 100
    remainder = cents % 100
    return f"${dollars}.{remainder:02d}"

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        try:
            cents = int(sys.argv[1])
            print(format_cents(cents))
        except ValueError:
            pass
