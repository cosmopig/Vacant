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
    # The task doesn't specify input format, but usually it's space-separated integers.
    # Since the prompt says "Write the code in a file called solution.py", 
    # I will provide a function and a simple way to call it if needed, 
    # or just the logic as requested.
    # Let's make it read from stdin for completeness.
    input_data = sys.stdin.read().split()
    if len(input_data) >= 2:
        first = int(input_data[0])
        second = int(input_data[1])
        print(sum_range(first, second))
