import sys
import argparse

def chunks(xs, n):
    if n <= 0:
        # If n is not sensible (e.g., <= 0), we can decide how to handle it.
        # Given the prompt says "callers do not always pass something sensible",
        # and usually chunking by 0 or negative would be an error, 
        # but let's just return the original list as one chunk if n is non-positive,
        # or raise a ValueError. Let's go with returning the list in one chunk 
        # or handling it gracefully. Actually, standard behavior for such tasks 
        # often expects an error or a default. I'll treat n <= 0 as 1 to avoid infinite loops.
        n = 1
    
    result = []
    for i in range(0, len(xs), n):
        result.append(xs[i:i + n])
    return result

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
