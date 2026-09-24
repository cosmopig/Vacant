def solve(n):
    if n == 10: return "ten"
    if n == 11: return "eleven"
    if n == 12: return "twelve"
    if n == 13: return "thirteen"
    if n == 14: return "fourteen"
    
    # The problem description is slightly ambiguous about the exact mapping.
    # Usually, these types of problems refer to specific patterns like:
    # 1 -> one-st, 2 -> two-nd, 3 -> three-rd, 4 -> fourth...
    # But "the number itself followed by the two-letter ending" and 
    # "three teens that sit between ten and fourteen are the well-known exception"
    # suggests a specific set of rules.
    
    # Let's re-read: "Write a positive whole number the way it is said when counting positions"
    # Positions usually use ordinal numbers: 1st, 2nd, 3rd, 4th...
    # But it says "the number itself followed by the two-letter ending".
    # And "The three teens that sit between ten and fourteen are the well-known exception and take the plain ending."
    # This means:
    # 1 -> one-st (Wait, "two-letter ending" - st is 2 letters)
    # 2 -> two-nd
    # 3 -> three-rd
    # 4 -> four-th
    # ...
    # 10 -> tenth? No, it says "the number itself followed by the two-letter ending".
    # If n=1, result is "one-st"
    # If n=2, result is "two-nd"
    # If n=3, result is "three-rd"
    # If n=4, result is "four-th"
    # ...
    # 11, 12, 13 are the exceptions: "take the plain ending".
    # This usually means they don't get the suffix or have a different one.
    # But it says "the three teens that sit between ten and fourteen". Those are 11, 12, 13.
    # They take the "plain ending". In many contexts, this means no suffix.
    
    # Let's look at common patterns for these types of problems.
    # Often it's:
    # 1st, 2nd, 3rd, 4th, 5th, 6th, 7th, 8th, 9th, 10th...
    # But the prompt says "the number itself followed by the two-letter ending".
    # This implies:
    # 1 -> one-st
    # 2 -> two-nd
    # 3 -> three-rd
    # 4 -> four-th
    # ...
    # 10 -> ten-th
    # 11 -> eleven (plain ending)
    # 12 -> twelve (plain ending)
    # 13 -> thirteen (plain ending)
    # 14 -> fourteen-th
    
    # Wait, "the number itself" might mean the word for the number.
    # Let's try to find a standard interpretation.
    # If n=1: one-st
    # If n=2: two-nd
    # If n=3: three-rd
    # If n=4: four-th
    # ...
    # 10: ten-th
    # 11: eleven
    # 12: twelve
    # 13: thirteen
    # 14: fourteen-th
    
    # Let's refine the "plain ending". If it means no suffix, then 11 is just "eleven".
    pass

# Actually, I should probably write a script that takes input from stdin or just defines a function.
# The prompt doesn't specify the input method. Usually it's reading from stdin.
