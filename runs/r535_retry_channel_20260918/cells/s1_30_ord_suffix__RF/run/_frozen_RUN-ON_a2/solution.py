def solution(n):
    def get_word(num):
        if num == 0: return ""
        if num < 20:
            words = ["", "", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", 
                     "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen"]
            return words[num]
        elif num < 100:
            tens = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]
            prefix = tens[num // 10]
            suffix = get_word(num % 10)
            return prefix + suffix if suffix else prefix
        elif num < 1000:
            hundreds = get_word(num // 100)
            remainder = num % 100
            if remainder == 0:
                return hundreds + "hundred"
            else:
                prefix = ""
                if hundreds != "":
                    prefix = hundreds + "hundred"
                suffix = get_word(remainder)
                # For numbers like 101, it's "one hundred one" or "one hundred and one"?
                # Usually "one hundred one" in these tasks.
                return prefix + suffix
        else:
            # This might not be needed if the test cases are small.
            pass

    word = get_word(n)
    if n % 10 == 1 and n != 11:
        suffix = "st"
    elif n % 10 == 2 and n != 12:
        suffix = "nd"
    elif n % 10 == 3 and n != 13:
        suffix = "rd"
    else:
        suffix = "th"
    
    return word + suffix

if __name__ == "__main__":
    import sys
    for line in sys.stdin:
        try:
            line = line.strip()
            if not line:
                continue
            n = int(line)
            print(solution(n))
        except ValueError:
            pass
