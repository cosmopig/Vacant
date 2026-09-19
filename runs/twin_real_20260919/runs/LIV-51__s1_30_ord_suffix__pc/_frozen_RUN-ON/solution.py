def ord_suffix(n):
    if 13 <= n <= 15:
        return str(n) + "th"
    
    # Standard suffixes for numbers ending in 1, 2, 3 (except 11, 12, 13)
    # and 0, 4, 5, 6, 7, 8, 9.
    # Wait, the prompt says "the number itself followed by the two-letter ending that goes with it".
    # Usually, these are:
    # 1st, 2nd, 3rd, 4th, 5th, 6th, 7th, 8th, 9th, 10th, 11th, 12th, 13th, 14th...
    # But the prompt says "The three teens that sit between ten and fourteen are the well-known exception".
    # These are 11, 12, 13. Wait, "between ten and fourteen" usually means 11, 12, 13.
    # Let's re-read: "The three teens that sit between ten and fourteen are the well-known exception and take the plain ending."
    # Plain ending is "th".
    # So 1st, 2nd, 3rd are special? No, they have unique endings.
    # Let's look at common ordinal suffixes:
    # 1 -> st
    # 2 -> nd
    # 3 -> rd
    # others -> th
    # Exceptions: 11th, 12th, 13th (they take 'th' instead of 'st', 'nd', 'rd').
    
    if n % 10 == 1 and n % 100 != 11:
        return str(n) + "st"
    elif n % 10 == 2 and n % 100 != 12:
        return str(n) + "nd"
    elif n % 10 == 3 and n % 100 != 13:
        return str(n) + "rd"
    else:
        return str(n) + "th"

# Wait, the prompt says "two-letter ending". 
# "st", "nd", "rd", "th" are all two letters.
# Let's double check the "three teens between ten and fourteen".
# Those are 11, 12, 13. They take "th".
# So if n=1, it's 1st. If n=2, it's 2nd. If n=3, it's 3rd.
# If n=11, it's 11th (not 11st).
# If n=12, it's 12th (not 12nd).
# If n=13, it's 13th (not 13rd).

def ord_suffix(n):
    if 11 <= n % 100 <= 13:
        return str(n) + "th"
    elif n % 10 == 1:
        return str(n) + "st"
    elif n % 10 == 2:
        return str(n) + "nd"
    elif n % 10 == 3:
        return str(n) + "rd"
    else:
        return str(n) + "th"
