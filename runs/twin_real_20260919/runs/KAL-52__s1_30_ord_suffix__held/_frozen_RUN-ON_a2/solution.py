def solve(n):
    if n == 11 or n == 12 or n == 13:
        return str(n)
    
    if n % 100 in [11, 12, 13]:
        # This part might be needed if it's for larger numbers too, but the prompt says "the three teens"
        pass

    last_digit = n % 10
    if last_digit == 1:
        return f"{n}st"
    elif last_digit == 2:
        return f"{n}nd"
    elif last_digit == 3:
        return f"{n}rd"
    else:
        return f"{n}th"

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        print(solve(int(sys.argv[1])))
