def solution(n):
    # Ordinal endings
    if n % 100 in [11, 12, 13]:
        ending = "th"
    else:
        last_digit = n % 10
        if last_digit == 1:
            ending = "st"
        elif last_digit == 2:
            ending = "nd"
        elif last_digit == 3:
            ending = "rd"
        else:
            ending = "th"

    # Number words
    ones = ["", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]
    teens = ["ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen"]
    tens = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]

    if n < 10:
        word = ones[n]
    elif n < 20:
        word = teens[n - 10]
    else:
        ten_part = (n // 10) * 10
        one_part = n % 10
        if one_part == 0:
            word = tens[n // 10]
        else:
            # For numbers like 21, the word is "twenty-one"
            # The prompt says "the number itself followed by the two-letter ending"
            # If n=21, and it's said as "twenty-first", then "number itself" might be "twenty" or "twenty-one"?
            # But usually "twenty-first" is one word. 
            # However, the prompt says "the number itself followed by...".
            # If n=21, and I use "twenty-one" + "-st", it's "twenty-one-st".
            word = tens[n // 10] + "-" + ones[one_part]

    return f"{word}-{ending}"

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        print(solution(int(sys.argv[1])))
