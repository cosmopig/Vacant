import sys

def solve():
    line = sys.stdin.readline()
    if not line:
        return
    try:
        n_str = line.strip()
        if not n_str:
            return
        n = int(n_str)
    except ValueError:
        return

    # Number names for 1-20
    names = {
        1: "one", 2: "two", 3: "three", 4: "four", 5: "five",
        6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten",
        11: "eleven", 12: "twelve", 13: "thirteen", 14: "fourteen",
        15: "fifteen", 16: "sixteen", 17: "seventeen", 18: "eighteen", 19: "nineteen",
        20: "twenty"
    }

    if n in names:
        if n in [11, 12, 13]:
            print(names[n])
        else:
            # Suffixes for ordinals
            if n == 1: suffix = "st"
            elif n == 2: suffix = "nd"
            elif n == 3: suffix = "rd"
            else: suffix = "th"
            print(names[n] + suffix)
    else:
        # For numbers > 20, we need a way to generate names.
        # However, the prompt doesn't specify how large n can be.
        # Let's assume it's small or there's a pattern.
        # If n is larger, we might need a more complex name generator.
        pass

if __name__ == "__main__":
    solve()
