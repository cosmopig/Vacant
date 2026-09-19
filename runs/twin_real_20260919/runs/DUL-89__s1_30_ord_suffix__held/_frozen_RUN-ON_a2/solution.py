import sys

def solve():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            n = int(line)
            # The three teens that sit between ten and fourteen are 11, 12, 13.
            # They take the "plain ending". In ordinal numbers, this usually means "th",
            # but the prompt says they are an exception to "the number itself followed by the two-letter ending".
            # If 1st, 2nd, 3rd are standard, then 11th, 12th, 13th would be the normal ones.
            # But it says they take the plain ending. This might mean "11", "12", "13" or "11th", "12th", "13th".
            # Wait, if 1st is "1st", then "plain ending" for 11 could be "11th"? No, that's the standard.
            # Let's re-read: "the number itself followed by the two-letter ending that goes with it."
            # This means 1 -> 1st, 2 -> 2nd, 3 -> 3rd, 4 -> 4th...
            # "The three teens ... are the well-known exception and take the plain ending."
            # If they take the "plain ending", it might mean no suffix at all.
            
            if n in [11, 12, 13]:
                print(n)
            else:
                if n % 10 == 1 and (n % 100 != 11):
                    print(f"{n}st")
                elif n % 10 == 2 and (n % 100 != 12):
                    print(f"{n}nd")
                elif n % 10 == 3 and (n % 100 != 13):
                    print(f"{n}rd")
                else:
                    print(f"{n}th")
        except ValueError:
            pass

if __name__ == "__main__":
    solve()
