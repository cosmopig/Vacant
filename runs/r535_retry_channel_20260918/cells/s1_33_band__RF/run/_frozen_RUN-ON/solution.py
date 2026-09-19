def solve():
    # The task asks to turn a mark out of one hundred into a single letter.
    # However, the prompt doesn't specify the input value. 
    # Usually, in these types of tasks, there might be an input or it's a logic puzzle.
    # Re-reading: "Turn a mark out of one hundred..." 
    # Wait, is "a mark" a specific number? 
    # "a mark" often refers to the score itself.
    # Let's look at the description again.
    # "Ninety and above is the top letter (A), eighty and above the next one down (B),
    # seventy and above the one after that (C), sixty and above the one after that (D), 
    # and anything lower is the fifth letter used -- which is not the fifth letter of the alphabet."
    # The fifth letter of the alphabet is E. So it's F? Or maybe something else?
    # "which is not the fifth letter of the alphabet" -> If E is the 5th, and it's NOT E, 
    # then what is it? Usually, in US schools, grades are A, B, C, D, F.
    # F is the 6th letter.
    
    # Wait, "Turn a mark out of one hundred". Is there an input?
    # If no input is provided, maybe I should read from stdin or it's a specific number hidden in the text?
    # "a mark" ... could it be 100? Or is it just asking for the logic?
    # Let's check if there are any other files. No.
    
    # Looking at the prompt again: "Turn a mark out of one hundred into the single letter..."
    # This sounds like a function or a script that takes an input.
    # Since no input is specified, I will assume it reads from stdin.
    
    import sys
    input_data = sys.stdin.read().strip()
    if not input_data:
        return

    try:
        score = int(input_data)
    except ValueError:
        return

    if score >= 90:
        print('A')
    elif score >= 80:
        print('B')
    elif score >= 70:
        print('C')
    elif score >= 60:
        print('D')
    else:
        # "anything lower is the fifth letter used -- which is not the fifth letter of the alphabet"
        # Alphabet: A(1), B(2), C(3), D(4), E(5), F(6)
        # Fifth letter of alphabet is E. 
        # The fifth letter used in schools is usually F.
        print('F')

if __name__ == "__main__":
    solve()
