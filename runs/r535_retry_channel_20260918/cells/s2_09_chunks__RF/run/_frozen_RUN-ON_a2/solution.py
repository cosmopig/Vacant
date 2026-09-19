import argparse
import sys

def chunks(xs, n):
    if n <= 0:
        raise ValueError("Chunk size must be a positive integer.")
    return [xs[i : i + n] for i in range(0, len(xs), n)]

def main():
    parser = argparse.ArgumentParser(description="Cut a list into consecutive pieces of size n.")
    parser.add_argument("xs", nargs='*', help="The list of elements to chunk.")
    parser.add_argument("-n", type=int, required=True, help="The size of each chunk.")
    
    args = parser.parse_args()
    
    try:
        result = chunks(args.xs, args.n)
        print(result)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
