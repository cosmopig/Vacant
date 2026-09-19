def chunks(xs, n):
    if n <= 0:
        raise ValueError("n must be positive")
    
    return [xs[i : i + n] for i in range(0, len(xs), n)]

if __name__ == "__main__":
    import sys
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("xs", nargs="+")
    parser.add_argument("-n", type=int, required=True)
    args = parser.parse_args()

    try:
        result = chunks(args.xs, args.n)
        print(result)
    except ValueError as e:
        print(e)
