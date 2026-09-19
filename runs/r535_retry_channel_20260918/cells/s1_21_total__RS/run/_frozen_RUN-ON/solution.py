def sum_range(first, second):
    if first > second:
        return 0
    # Using the arithmetic series formula: sum = n * (a + l) / 2
    # where n is number of terms, a is first term, l is last term.
    n = second - first + 1
    return n * (first + second) // 2

if __name__ == "__main__":
    import sys
    if len(sys.argv) == 3:
        try:
            f = int(sys.argv[1])
            s = int(sys.argv[2])
            print(sum_range(f, s))
        except ValueError:
            pass
