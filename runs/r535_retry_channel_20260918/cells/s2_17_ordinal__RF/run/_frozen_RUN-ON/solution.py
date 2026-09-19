def ordinal(n):
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"

if __name__ == "__main__":
    # Example usage (optional, but good for testing)
    for i in range(1, 25):
        print(f"{i}: {ordinal(i)}")
