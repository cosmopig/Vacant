import sys
import argparse

def chunks(xs, n):
    if n <= 0:
        # If n is not sensible (e.g., <= 0), we could return the list as is or raise an error.
        # Given "callers do not always pass something sensible", returning the original list
        # or handling it gracefully is good. Let's just return [xs] if n <= 0 to avoid infinite loops.
        return [xs]
    
    result = []
    for i in range(0, len(xs), n):
        result.append(xs[i:i + n])
    return result

def main():
    parser = argparse.ArgumentParser(description="Chunk a list into pieces of size n.")
    parser.add_argument("data", nargs='*', help="The list elements")
    parser.add_argument("-n", type=int, default=1, help="The size of each chunk")
    
    args = parser.parse_args()
    
    # The task says "The size arrives from a command line flag"
    # and "chunks(xs, n)" takes a list. 
    # Since the input is a list of items, we'll treat positional arguments as the list elements.
    
    result = chunks(args.data, args.n)
    print(result)

if __name__ == "__main__":
    main()
