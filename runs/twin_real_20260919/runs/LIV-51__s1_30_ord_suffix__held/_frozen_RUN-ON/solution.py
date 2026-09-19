def solve(n):
    ordinals = {
        1: "first",
        2: "second",
        3: "third",
        4: "fourth",
        5: "fifth",
        6: "sixth",
        7: "seventh",
        8: "eighth",
        9: "ninth",
        10: "tenth",
        11: "eleven",
        12: "twelve",
        13: "thirteen",
        14: "fourteenth"
    }
    if n in ordinals:
        return ordinals[n]
    
    # For numbers > 14, we need a general rule.
    # The prompt says "the number itself followed by the two-letter ending".
    # This suggests that for n > 14, we should use the word for n and add "th".
    # But how to get the word for n? We need a way to convert an integer to its English word.
    
    def number_to_words(num):
        if num == 0: return ""
        units = ["", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", 
                  "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen"]
        tens = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]
        
        if num < 20:
            return units[num]
        elif num < 100:
            ten_part = tens[num // 10]
            unit_part = number_to_words(num % 10)
            return ten_part + (" " + unit_part if unit_part else "")
        else:
            thousand_part = num // 1000
            hundred_part = (num % 1000) // 100
            remainder_part = num % 1000
            
            res = ""
            if thousand_part > 0:
                res += number_to_words(thousand_part) + " thousand"
            if hundred_part > 0:
                res += (" " if res else "") + number_to_words(hundred_part) + " hundred"
            if remainder_part > 0:
                res += (" " if res else "") + number_to_words(remainder_part)
            return res

    # Wait, the prompt says "the number itself followed by the two-letter ending".
    # If n=15, is it "fifteenth"? Yes.
    # If n=20, is it "twentieth"? Yes.
    # So we need to convert the number to its word and then add "th" (or handle special cases like 20 -> twentieth).

    # Let's refine the ordinal conversion for numbers > 14.
    def get_ordinal(num):
        if num == 1: return "first"
        if num == 2: return "second"
        if num == 3: return "third"
        if num == 11: return "eleven"
        if num == 12: return "twelve"
        if num == 13: return "thirteen"
        
        # For others, we need to handle the word and suffix.
        # This is getting complicated. Let's see if there's a simpler way.
        pass

    # Actually, I should probably just use a library or a more robust way to get these words.
    # But I can only use standard libraries.
    pass
