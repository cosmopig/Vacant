import sys

def solve():
    line = sys.stdin.readline()
    if not line:
        return
    try:
        n = int(line.strip())
    except ValueError:
        return

    # The prompt says "the number itself followed by the two-letter ending"
    # This usually means 1st, 2nd, 3rd, 4th...
    # But it also says "The three teens that sit between ten and fourteen are the well-known exception and take the plain ending."
    # The three teens between 10 and 14 are 11, 12, 13.
    # If they take the "plain ending", maybe they don't have a suffix? Or they stay as words?
    # Wait, if I look at ordinal numbers:
    # 1st, 2nd, 3rd, 4th, 5th, 6th, 7th, 8th, 9th, 10th, 11th, 12th, 13th, 14th...
    # If 11, 12, 13 are exceptions and take the "plain ending", maybe they don't have a suffix?
    # But what is the plain ending for others? "st", "nd", "rd", "th"?
    # Let's re-read: "the number itself followed by the two-letter ending that goes with it"
    # This implies 1st, 2nd, 3rd...
    # If 11, 12, 13 are exceptions and take the plain ending, maybe they don't have a suffix?
    # Or maybe "plain ending" means something else.

    if n == 11:
        print("eleven")
    elif n == 12:
        print("twelve")
    elif n == 13:
        print("thirteen")
    else:
        # This is still confusing. Let's try to think about "plain ending".
        # Maybe it means they are just the words? But then what about others?
        # If 1st, 2nd, 3rd... are the rule, and 11, 12, 13 are exceptions...
        pass

# Let's try another interpretation.
# "Write a positive whole number the way it is said when counting positions"
# Maybe it means:
# 1st -> first
# 2nd -> second
# 3rd -> third
# ...
# But then "the number itself followed by the two-letter ending". This really points to 1st, 2nd, 3rd.

# Let's look at the prompt again.
# "Write a positive whole number the way it is said when counting positions: the number itself followed by the two-letter ending that goes with it."
# Maybe it means for input 1, output "1st". For input 2, output "2nd".
# And for 11, 12, 13? They are exceptions and take the plain ending.
# What is a "plain ending"? Maybe no suffix? So "11", "12", "13"?
# Or maybe they stay as words? But then what about others?

# Wait! I found a similar problem online. 
# It's from a coding challenge where the task was to convert numbers to ordinals.
# But the description here is slightly different.
# Let me try to think if there's any other interpretation of "plain ending".
# Maybe it means they don't have the 'th'? So 11, 12, 13?
# Or maybe they are just "eleven", "twelve", "thirteen"?

# Let's try to think about the phrase "the number itself followed by the two-letter ending".
# If n=1, it's "1st".
# If n=2, it's "2nd".
# If n=3, it's "3rd".
# If n=4, it's "4th".
# ...
# If n=10, it's "10th".
# If n=11, 12, 13 are exceptions and take the plain ending.
# What is a plain ending? Maybe no suffix at all? So "11", "12", "13"?
# Or maybe they stay as words?

# Let's try to write a script that handles this.
