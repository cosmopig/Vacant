import sys
import argparse

def chunks(xs, n):
    if n <= 0:
        # If n is not sensible (e.g., <= 0), we can decide how to handle it.
        # Given the prompt says "callers do not always pass something sensible",
        # and usually chunking by 0 or negative doesn't make sense, 
        # returning the original list as one chunk or an empty list are options.
        # However, a common robust way is to treat non-positive n as 1 or just return xs.
        # Let's assume if it's not sensible (<=0), we return the list as is in one chunk
        # or handle it gracefully. For this task, let's ensure it doesn't crash.
        return [xs] if xs else []
    
    result = []
    for i in range(0, len(xs), n):
        result.append(xs[i:i + n])
    return result

def main():
    parser = argparse.ArgumentParser(description="Chunk a list into pieces of size n.")
    parser.add_argument("list", nargs="+", help="The list of elements to chunk")
    parser.add_argument("-n", type=int, default=1, help="The size of each chunk")
    
    args = parser.parse_args()
    
    # Convert input strings to integers if possible, otherwise keep as strings
    input_list = []
    for item in args.list:
        try:
            input_list.append(int(item))
        except ValueError:
            input_list.append(item)
            
    chunks_result = chunks(input_list, args.n)
    print(chunks_result)

if __name__ == "__main__":
    main()
