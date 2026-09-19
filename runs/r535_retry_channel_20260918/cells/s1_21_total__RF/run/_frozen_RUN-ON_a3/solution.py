def sum_range(first, second):
    if first > second:
        return 0
    return (second - first + 1) * (first + second) // 2

if __name__ == "__main__":
    import sys
    if len(sys.argv) == 3:
        f = int(sys.argv[1])
        s = int(sys.argv[2])
        print(sum_range(f, s))
