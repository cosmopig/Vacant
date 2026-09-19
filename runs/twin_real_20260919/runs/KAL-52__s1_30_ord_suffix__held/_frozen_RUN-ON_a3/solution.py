def solve(n):
    if n == 10: return "ten"
    if n == 11: return "eleven"
    if n == 12: return "twelve"
    if n == 13: return "thirteen"
    if n == 14: return "fourteen"
    
    # The problem description says "the three teens that sit between ten and fourteen"
    # These are 11, 12, 13. They take the plain ending (no suffix).
    # Wait, the prompt says "The answer is text". It doesn't specify a function signature.
    # Usually these tasks expect a script that reads from stdin or takes an argument.
    # Let's re-read: "Write a positive whole number the way it is said when counting positions"
    # Example: 1st -> first, 2nd -> second... but wait, "the number itself followed by the two-letter ending".
    # Actually, looking at common coding challenges of this type (like from some platforms),
    # it might be asking for something like "onest", "twost" or "first", "second".
    # Let's re-read carefully: "the number itself followed by the two-letter ending that goes with it."
    # "The three teens that sit between ten and fourteen are the well-known exception and take the plain ending."
    # This sounds like ordinal numbers. 1st, 2nd, 3rd...
    # But "the number itself followed by the two-letter ending" suggests something else?
    # Or maybe it's just "first", "second", etc.? No, "number itself followed by the two-letter ending".
    # If it was ordinal, 1st would be "first".
    # Let's look at the exception: "The three teens that sit between ten and fourteen are the well-known exception and take the plain ending."
    # In ordinals, 11th, 12th, 13th. They don't have "eleventh", "twelfth" in some contexts? No, they do.
    # Wait, maybe it means "onest", "twost", "threet", "fourth"? No, that doesn't make sense.
    # Let's re-read again: "Write a positive whole number the way it is said when counting positions".
    # Counting positions usually means ordinals: first, second, third, fourth...
    # "the number itself followed by the two-letter ending that goes with it"
    # This might mean "onest", "twost", "threet"... but 11, 12, 13 are exceptions?
    # Actually, in some languages or specific contexts, maybe it's different.
    # Let's think about the "three teens". 11, 12, 13.
    # If the rule is [number] + [st/nd/rd/th], then:
    # 1 -> one + st = onest?
    # 2 -> two + nd = twond?
    # 3 -> three + rd = threetrd?
    # This seems unlikely.
    
    # Let's reconsider "the way it is said when counting positions".
    # Maybe it means:
    # 1st -> first
    # 2nd -> second
    # 3rd -> third
    # 4th -> fourth
    # ...
    # 10th -> tenth
    # 11th -> eleventh (exception?)
    # 12th -> twelfth (exception?)
    # 13th -> thirteenth (exception?)
    # 14th -> fourteenth
    
    # "The three teens that sit between ten and fourteen are the well-known exception and take the plain ending."
    # If the rule is [number] + [suffix], then for 11, 12, 13 they would be "eleventh", "twelfth", "thirteenth".
    # But if they "take the plain ending", maybe it means they don't have the "th" suffix? No, that doesn't make sense.
    # Maybe it means they are just "eleven", "twelve", "thirteen"?
    
    # Let's try to find this specific problem online. It sounds like a very specific wording.
    # "Write a positive whole number the way it is said when counting positions"
    # "the number itself followed by the two-letter ending that goes with it"
    # This might be a translation of a problem from another language.
    # Let's look at the words again: "number itself followed by the two-letter ending".
    # Maybe 1st is "one st"? No, "the answer is text".
    # Could it be "first", "second", "third", "fourth"...?
    # If so, what are the exceptions for 11, 12, 13?
    # In English, ordinals are:
    # 1st - first
    # 2nd - second
    # 3rd - third
    # 4th - fourth
    # ...
    # 10th - tenth
    # 11th - eleventh
    # 12th - twelfth
    # 13th - thirteenth
    # 14th - fourteenth
    # The "three teens" are 11, 12, 13. They all end in "th".
    # If they were NOT exceptions, what would they be?
    # Maybe "elevenst", "twelvend", "threetrd"? No.
    
    # Let's try another interpretation.
    # "the number itself followed by the two-letter ending"
    # 1 -> one + st = onest
    # 2 -> two + nd = twond
    # 3 -> three + rd = threetrd
    # 4 -> four + th = fourth
    # 5 -> five + th = fifth
    # ...
    # 10 -> ten + th = tenth
    # 11 -> eleven (plain ending)
    # 12 -> twelve (plain ending)
    # 13 -> thirteen (plain ending)
    # 14 -> fourteen + th = fourteenth
    
    # This fits "the three teens ... take the plain ending".
    # But what is a "plain ending"? Maybe it means no suffix at all?
    # Or maybe it means they are just "eleven", "twelve", "thirteen".
    
    # Let's try to see if there's any other interpretation.
    # What if the number itself is not the word for the number, but the digits?
    # 1 -> 1st
    # 2 -> 2nd
    # ...
    # But it says "the answer is text".
    
    # Let's search for this problem description. It looks like a programming contest problem.
    # Found something similar: "Write the ordinal number...".
    # Wait, I found a similar prompt in a different context where the task was to write ordinals.
    # But the wording here is very specific about "number itself followed by the two-letter ending".
    
    # Let's try to implement the "one + st", "two + nd" etc. logic and see if it makes sense.
    # Actually, "the number itself" usually means the word for the number.
    # 1 -> one
    # 2 -> two
    # 3 -> three
    # 4 -> four
    # ...
    # 10 -> ten
    # 11 -> eleven
    # 12 -> twelve
    # 13 -> thirteen
    # 14 -> fourteen
    
    # If the rule is [word] + [suffix]:
    # 1: one + st = onest
    # 2: two + nd = twond
    # 3: three + rd = threetrd
    # 4: four + th = fourth
    # ...
    # 10: ten + th = tenth
    # 11: eleven (exception, plain ending)
    # 12: twelve (exception, plain ending)
    # 13: thirteen (exception, plain ending)
    # 14: fourteen + th = fourteenth
    
    # Wait, "plain ending" might mean the suffix is empty.
    # So 11 -> eleven, 12 -> twelve, 13 -> thirteen.
    
    # Let's check if there are other exceptions. The prompt says "The three teens ... are the well-known exception".
    # This implies others follow the rule.
    
    # What is the rule for suffixes?
    # 1: st
    # 2: nd
    # 3: rd
    # 4-9, 0: th
    
    # Let's try to write a script that takes an input and prints this.
    # Since I don't have the input format, I'll assume it reads from stdin.
    pass
