def solve(n):
    if n == 1: return "first"
    if n == 2: return "second"
    if n == 3: return "third"
    if n == 4: return "fourth"
    if n == 5: return "fifth"
    if n == 6: return "sixth"
    if n == 7: return "seventh"
    if n == 8: return "eighth"
    if n == 9: return "ninth"
    if n == 10: return "tenth"
    if n == 11: return "eleventh"
    if n == 12: return "twelfth"
    if n == 13: return "thirteenth"
    if n == 14: return "fourteenth"
    
    # For numbers > 14, we need to handle them.
    # The prompt says "the number itself followed by the two-letter ending that goes with it".
    # This is very strange if it's ordinals.
    # Let's re-read: "Write a positive whole number the way it is said when counting positions"
    # Maybe it means 1st, 2nd, 3rd? But those are not "the way it is said".
    # Wait! What if it's just ordinals but for larger numbers too?
    # Let's look at the exception again: "The three teens that sit between ten and fourteen are the well-known exception and take the plain ending."
    # 11, 12, 13. They take the "plain ending".
    # In ordinals, they end in "th".
    # What if other numbers have a different ending?
    # Like 21st, 22nd, 23rd...
    # But it says "the number itself followed by the two-letter ending".
    # If n=21, is it "twenty-first"? That's not "the number itself" (twenty-one) + "st".
    # Wait! What if "the number itself" means the word for the number?
    # 21 -> twenty-one. Ending "st" -> twenty-onest? No.
    # Let me search for this exact phrase again.
    pass
