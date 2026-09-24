import sys

def solve():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            n = int(line)
        except ValueError:
            continue

        # Ordinal suffix logic
        # 1st, 2nd, 3rd, 4th...
        # Exceptions are 11th, 12th, 13th (they take 'th' instead of 'st', 'nd', 'rd')
        
        if n % 100 in [11, 12, 13]:
            suffix = "th"
        else:
            last_digit = n % 10
            if last_digit == 1:
                suffix = "st"
            elif last_digit == 2:
                suffix = "nd"
            elif last_digit == 3:
                suffix = "rd"
            else:
                suffix = "th"
        
        print(f"{n}{suffix}")

if __name__ == "__main__":
    solve()
