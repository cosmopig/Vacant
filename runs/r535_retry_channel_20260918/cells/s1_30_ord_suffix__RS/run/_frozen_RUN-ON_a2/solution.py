def solution(n):
    if 10 <= n <= 19:
        return str(n) + "teen"
    
    # Handle the special case for 11, 12, 13 which are usually "eleven", "twelve", "thirteen"
    # but the prompt says "The three teens that sit between ten and fourteen are the well-known exception 
    # and take the plain ending." This is slightly ambiguous. 
    # Usually, counting positions means:
    # 1st -> first, 2nd -> second, 3rd -> third
    # 4th -> fourth, ... 10th -> tenth
    # 11th -> eleventh, 12th -> twelfth, 13th -> thirteenth
    # 14th -> fourteenth...
    # Wait, the prompt says "Write a positive whole number the way it is said when counting positions: 
    # the number itself followed by the two-letter ending that goes with it."
    # Example: 1st (first), 2nd (second), 3rd (third)
    # But then it says "The three teens that sit between ten and fourteen are the well-known exception 
    # and take the plain ending. The answer is text."
    # This sounds like a specific logic puzzle. Let's re-read carefully.
    
    # "the number itself followed by the two-letter ending"
    # 1st -> 1st? No, "the way it is said".
    # Maybe it means:
    # 1st -> first
    # 2nd -> second
    # 3rd -> third
    # 4th -> fourth
    # ...
    # 10th -> tenth
    # 11th -> eleventh (Wait, "The three teens that sit between ten and fourteen are the well-known exception")
    # Between 10 and 14 are 11, 12, 13.
    # If they take the "plain ending", maybe it means just the number? Or something else?
    
    # Let's look at common coding challenges like this.
    # Actually, looking at the prompt again: "the number itself followed by the two-letter ending that goes with it."
    # This might mean:
    # 1st -> first
    # 2nd -> second
    # 3rd -> third
    # 4th -> fourth
    # ...
    # 10th -> tenth
    # 11th -> eleventh? No, "take the plain ending".
    # Maybe it means:
    # 1st -> first
    # 2nd -> second
    # 3rd -> third
    # 4th -> fourth
    # ...
    # 10th -> tenth
    # 11th -> eleven
    # 12th -> twelve
    # 13th -> thirteen
    # 14th -> fourteenth
    
    # Let's re-read: "Write a positive whole number the way it is said when counting positions: 
    # the number itself followed by the two-letter ending that goes with it."
    # This usually refers to ordinal numbers.
    # 1st, 2nd, 3rd, 4th...
    # "The three teens that sit between ten and fourteen are the well-known exception and take the plain ending."
    # If 11th is "eleventh", it has a "th" ending. If it takes the "plain ending", maybe it's just "eleven"?
    
    # Wait, I might be overthinking. Let's look for this specific problem online.
    # It looks like a variation of a common programming task.
    # Actually, let me try to implement a standard ordinal converter and adjust for the exceptions.
    pass

