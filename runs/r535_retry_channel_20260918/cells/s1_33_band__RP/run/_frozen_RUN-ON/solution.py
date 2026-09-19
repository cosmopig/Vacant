def solve():
    # The task asks to turn a mark out of one hundred into a single letter.
    # However, the prompt doesn't specify the input value. 
    # Looking at the description again: "Turn a mark out of one hundred..."
    # Usually these tasks imply reading from stdin or a specific variable.
    # Since no input is provided in the task description other than the logic,
    # and it says "The answer is a single upper-case character", 
    # I will assume the input is provided via standard input.

    import sys
    input_data = sys.stdin.read().strip()
    if not input_data:
        return

    try:
        score = int(input_data)
    except ValueError:
        return

    # Logic:
    # 90 and above -> A (top letter)
    # 80 and above -> B (next one down)
    # 70 and above -> C (one after that)
    # 60 and above -> D (one after that)
    # anything lower -> F (fifth letter used -- which is not the fifth letter of the alphabet)
    # The fifth letter of the alphabet is E, so the "fifth letter used" is F.

    if score >= 90:
        print("A")
    elif score >= 80:
        print("B")
    elif score >= 70:
        print("C")
    elif score >= 60:
        print("D")
    else:
        print("F")

if __name__ == "__main__":
    solve()
