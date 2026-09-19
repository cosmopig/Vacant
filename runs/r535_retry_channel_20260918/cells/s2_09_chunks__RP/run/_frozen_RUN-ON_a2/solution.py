def chunks(xs, n):
    if n <= 0:
        raise ValueError("n must be a positive integer")
    
    result = []
    for i in range(0, len(xs), n):
        result.append(xs[i:i + n])
    return result

import sys
import argparse

def main():
    parser = argparse.ArgumentParser(description="Chunk a list into pieces of size n.")
    parser.add_argument("xs", nargs="+", help="The list of elements to chunk")
    parser.add_argument("-n", type=int, default=1, help="The size of each chunk")
    
    args = parser.parse_args()
    
    # The input xs are strings from command line, but the task implies a general list.
    # Since we only have command line arguments, we'll treat them as strings.
    chunks_result = chunks(args.xs, args.n)
    print(chunks_result)

if __name__ == "__main__":
    main()
