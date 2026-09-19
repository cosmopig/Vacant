def solution(n):
    # The task is to write a positive whole number the way it is said when counting positions.
    # "the number itself followed by the two-letter ending that goes with it."
    # Example: 1st -> one + st = onest? No, usually these are ordinals like first, second, third.
    # But the prompt says "the number itself". This is very specific.
    # Let's look at the exceptions: "The three teens that sit between ten and fourteen are the well-known exception 
    # and take the plain ending."
    # These are 11, 12, 13. They take the "plain ending".
    # If others are "number + suffix", then maybe these are just "number"?
    # Or maybe it's:
    # 1 -> first
    # 2 -> second
    # 3 -> third
    # 4 -> fourth
    # ...
    # But if so, what does "the number itself followed by the two-letter ending" mean?
    # Maybe it means:
    # 1st -> one + st = onest
    # 2nd -> two + nd = twond
    # 3rd -> three + rd = threetrd
    # 4th -> four + th = fourth
    # ...
    # And for 11, 12, 13 they are "eleven", "twelve", "thirteen" (plain ending).

    # Let's try to find this exact problem. It looks like a variation of an old programming challenge.
    # Actually, I found a similar one: "Write the ordinal number for a given integer."
    # But the wording here is very different. 
    # "the number itself followed by the two-letter ending"
    # Let's try to implement it as:
    # 1 -> onest
    # 2 -> twond
    # 3 -> threetrd
    # 4 -> fourth
    # ...
    # and for 11, 12, 13 they are just "eleven", "twelve", "thirteen".

    # Wait, if it's counting positions:
    # 1st, 2nd, 3rd, 4th, 5th, 6th, 7th, 8th, 9th, 10th, 11th, 12th, 13th, 14th...
    # The "three teens" are 11, 12, 13. They take the "plain ending".
    # If others have a suffix (st, nd, rd, th), then maybe these don't?
    # But they always have "th" in ordinals! 11th, 12th, 13th.
    # So if they take the "plain ending", it might mean they DON'T have a suffix?
    # That would be weird for counting positions.

    # Let's re-read: "the number itself followed by the two-letter ending that goes with it."
    # This really sounds like concatenation.
    # 1 -> one + st = onest
    # 2 -> two + nd = twond
    # 3 -> three + rd = threetrd
    # 4 -> four + th = fourth
    # ...
    # 10 -> ten + th = tenth
    # 11 -> eleven (plain ending)
    # 12 -> twelve (plain ending)
    # 13 -> thirteen (plain ending)
    # 14 -> fourteen + th = fourteenth? No, "the number itself followed by the two-letter ending".
    # If it's counting positions, maybe 14 is "fourteen" + "th"?

    # Let's try another interpretation. Maybe "the number itself" means the ordinal word?
    # But then what is "the two-letter ending"?
    # In "first", there is no two-letter ending.
    # In "fourth", "th" is a two-letter ending.

    # Let's try to think about "plain ending". 
    # If the others are "number + suffix", then "plain ending" means just "number".
    # So:
    # 1 -> onest
    # 2 -> twond
    # 3 -> threetrd
    # 4 -> fourth
    # ...
    # 10 -> tenth
    # 11 -> eleven
    # 12 -> twelve
    # 13 -> thirteen
    # 14 -> fourteenth

    # Let's try to write a solution that handles this.
    pass
