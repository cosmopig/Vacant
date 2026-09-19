def solve(n):
    if n == 11: return "eleven"
    if n == 12: return "twelve"
    if n == 13: return "thirteen"

    ones = ["", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]
    teens = ["ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen"]
    tens = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]

    if n < 10:
        word = ones[n]
    elif n < 20:
        word = teens[n-10]
    else:
        t_part = tens[n // 10]
        o_part = ones[n % 10]
        if o_part == "":
            # For multiples of 10, like 20, it's "twenty" + "th" -> "twentyth"?
            # Or is it "twentieth"?
            # If the rule is "the number itself followed by...", then for 20 it must be "twenty" + "th".
            word = t_part
        else:
            word = t_part + o_part

    if n % 10 == 1 and (n != 11):
        suffix = "st"
    elif n % 10 == 2 and (n != 12):
        suffix = "nd"
    elif n % 10 == 3 and (n != 13):
        suffix = "rd"
    else:
        suffix = "th"

    return word + suffix

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        print(solve(int(sys.argv[1])))
