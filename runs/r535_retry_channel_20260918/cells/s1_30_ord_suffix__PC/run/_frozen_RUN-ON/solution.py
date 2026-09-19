def ord_suffix(n):
    if n < 0 or not isinstance(n, int) or n == 0:
        return ""
    
    # Special cases for teens (11, 12, 13)
    if 11 <= n <= 13:
        return str(n) + "th" # Wait, the prompt says "take the plain ending". 
        # Actually, let's re-read. "The three teens that sit between ten and fourteen are the well-known exception and take the plain ending."
        # Usually "plain ending" means no suffix or a specific one? 
        # Let's look at common patterns: 1st, 2nd, 3rd, 4th... 11th, 12th, 13th.
        # Wait, if they take the "plain ending", and others have suffixes like "st", "nd", "rd", "th".
        # Let's re-read carefully: "Write a positive whole number the way it is said when counting positions: the number itself followed by the two-letter ending that goes with it."
        # Examples of endings: 1st, 2nd, 3rd, 4th, 5th... 10th, 11th, 12th, 13th, 14th.
        # "The three teens ... take the plain ending." This usually means they don't follow the st/nd/rd rule but use 'th'.
        # But wait, if I say "eleventh", it ends in "th". If I say "first", it ends in "st".
        # Let's check common interpretations of this specific problem (it looks like a standard coding challenge).
        # Usually: 1 -> 1st, 2 -> 2nd, 3 -> 3rd, 4 -> 4th ... 10 -> 10th, 11 -> 11th, 12 -> 12th, 13 -> 13th, 14 -> 14th.
        # Wait, if 11, 12, 13 take the "plain ending", and others have suffixes...
        # Let's re-read: "the number itself followed by the two-letter ending that goes with it."
        # This is confusing. "two-letter ending"? "st" is 2 letters. "nd" is 2 letters. "rd" is 2 letters. "th" is 2 letters.
        # So all of them are two-letter endings?
        # If 11, 12, 13 take the "plain ending", maybe it means they don't have a special suffix like st/nd/rd and just use th?
        # But 4th also uses th.
        # Let's look at the wording again: "the number itself followed by the two-letter ending that goes with it."
        # Maybe for 1, it's "st". For 2, it's "nd". For 3, it's "rd". For others, it's "th".
        # And for 11, 12, 13 they are exceptions?
        # Actually, in English:
        # 1st, 2nd, 3rd, 4th, 5th, 6th, 7th, 8th, 9th, 10th, 11th, 12th, 13th, 14th...
        # The "exceptions" are usually 11, 12, 13 because they don't end in st, nd, rd despite ending in 1, 2, 3.
        # So if the rule is:
        # ends in 1 -> st
        # ends in 2 -> nd
        # ends in 3 -> rd
        # else -> th
        # Then 11, 12, 13 would be "11st", "12nd", "13rd" if they followed the rule.
        # But they are exceptions and take the "plain ending" (th).
        # So:
        # 1 -> 1st
        # 2 -> 2nd
        # 3 -> 3rd
        # 4-10 -> 4th-10th
        # 11-13 -> 11th-13th (plain ending)
        # 14+ -> follow the rule? Or just th?
        # "the number itself followed by the two-letter ending that goes with it."
        # Let's try to implement this logic.
        pass

def ord_suffix(n):
    if n <= 0: return "" # Should not happen based on prompt "positive whole number"
    
    # The rule seems to be:
    # If ends in 1 and not 11 -> st
    # If ends in 2 and not 12 -> nd
    # If ends in 3 and not 13 -> rd
    # Else -> th
    
    if n % 10 == 1 and n % 100 != 11:
        return f"{n}st"
    elif n % 10 == 2 and n % 100 != 12:
        return f"{n}nd"
    elif n % 10 == 3 and n % 100 != 13:
        return f"{n}rd"
    else:
        return f"{n}th"
