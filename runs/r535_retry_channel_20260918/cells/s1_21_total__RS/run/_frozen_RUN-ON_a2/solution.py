def sum_range(first, second):
    if first > second:
        return 0
    # The sum of numbers from 1 to n is (n * (n + 1)) // 2
    # Sum from a to b is sum(1..b) - sum(1..a-1)
    def sum_to_n(n):
        return (n * (n + 1)) // 2
    
    return sum_to_n(second) - sum_to_n(first - 1)

if __name__ == "__main__":
    import sys
    # Example usage: python solution.py 1 10
    if len(sys.argv) == 3:
        try:
            f = int(sys.argv[1])
            s = int(sys.argv[2])
            print(sum_range(f, s))
        except ValueError:
            pass
