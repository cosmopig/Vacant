def solve(n):
    if n == 10: return "ten"
    if n == 11: return "eleven"
    if n == 12: return "twelve"
    if n == 13: return "thirteen"
    if n == 14: return "fourteen"
    
    # This task seems to be about the suffix of numbers in English.
    # However, the prompt says "Write a positive whole number the way it is said when counting positions".
    # Usually, this refers to ordinal numbers (first, second, third...).
    # But then it says "the number itself followed by the two-letter ending that goes with it".
    # And "The three teens... take the plain ending".
    
    # Let's re-read: "Write a positive whole number the way it is said when counting positions"
    # Example: 1 -> first, 2 -> second, 3 -> third, 4 -> fourth, 5 -> fifth...
    # Wait, "the number itself followed by the two-letter ending".
    # If n=1, maybe it's "onest"? No.
    # Maybe it means ordinal numbers but with a specific rule?
    # "The three teens that sit between ten and fourteen are the well-known exception and take the plain ending."
    # 11 -> eleventh (plain ending?)
    # 12 -> twelfth (plain ending?)
    # 13 -> thirteenth (plain ending?)
    
    # Let's look at common "two-letter endings" for positions:
    # 1st, 2nd, 3rd, 4th, 5th...
    # The suffixes are st, nd, rd, th.
    # "the number itself followed by the two-letter ending"
    # If n=1, is it "one st"? Or "first"?
    # "The answer is text."
    
    # Let's re-read again: "Write a positive whole number the way it is said when counting positions".
    # This usually means ordinal numbers.
    # 1st = first
    # 2nd = second
    # 3rd = third
    # 4th = fourth
    # ...
    # But then "the number itself followed by the two-letter ending that goes with it".
    # This is confusing. Let's try to find a pattern.
    # Maybe it means:
    # 1 -> first
    # 2 -> second
    # 3 -> third
    # 4 -> fourth
    # ...
    # But "the number itself followed by the two-letter ending".
    # If n=1, and suffix is "st", then "one st"? No.
    
    # Let's look at the "three teens" exception:
    # 11, 12, 13 are between 10 and 14.
    # They take the "plain ending".
    # In ordinal numbers:
    # 11th -> eleventh
    # 12th -> twelfth
    # 13th -> thirteenth
    # These all end in "th".
    
    # Wait, maybe it's simpler. Maybe it's just the word for the number + suffix?
    # No, "the way it is said when counting positions" usually means first, second...
    pass

def solve_v2(n):
    # Let's try to interpret "the number itself followed by the two-letter ending".
    # Maybe it's like: 1st -> one st? No.
    # What if it's just ordinal numbers, but for some reason they call them "two-letter endings"?
    # That doesn't make sense.
    pass
