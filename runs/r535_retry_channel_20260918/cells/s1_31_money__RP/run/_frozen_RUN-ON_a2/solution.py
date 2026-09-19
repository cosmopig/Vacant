def money(cents):
    dollars = cents // 100
    remaining_cents = cents % 100
    return f"${dollars}.{remaining_cents:02d}"

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        try:
            input_cents = int(sys.argv[1])
            print(money(input_cents))
        except ValueError:
            pass
