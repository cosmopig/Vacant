import sys

def solve():
    # The task doesn't specify the input source, but usually it's from stdin or an argument.
    # Since "Nothing else is read" and I need to provide a solution, 
    # let's assume the mark is provided as a command line argument or via stdin.
    # However, looking at the prompt again: "Turn a mark out of one hundred..."
    # It might be that I need to write a script that takes an input and prints the letter.
    
    try:
        line = sys.stdin.read().strip()
        if not line:
            return
        mark = int(line)
    except EOFError:
        return
    except ValueError:
        return

    if mark >= 90:
        print("A")
    elif mark >= 80:
        print("B")
    elif mark >= 70:
        print("C")
    elif mark >= 60:
        print("D")
    else:
        # The fifth letter used in American schools is F.
        # E is the fifth letter of the alphabet, but it's not used as a grade.
        print("F")

if __name__ == "__main__":
    solve()
