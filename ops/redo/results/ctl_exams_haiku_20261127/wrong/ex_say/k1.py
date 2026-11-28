SMALL = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
         "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
         "seventeen", "eighteen", "nineteen"]
TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]
SCALES = [(10**9, "billion"), (10**6, "million"), (10**3, "thousand")]


def _below_thousand(n):
    words = []
    hundreds, rest = divmod(n, 100)
    if hundreds:
        words.append(SMALL[hundreds] + " hundred")
    if rest:
        if rest < 20:
            words.append(SMALL[rest])
        else:
            tens, ones = divmod(rest, 10)
            words.append(TENS[tens] + ("-" + SMALL[ones] if ones else ""))
    return " ".join(words)


def say(number):
    if number < 0 or number >= 10**12:
        raise ValueError("input out of range")
    if number == 0:
        return "zero"
    words = []
    for value, name in SCALES:
        chunk, number = divmod(number, value)
        if chunk:
            words.append(_below_thousand(chunk) + " " + name)
    if number:
        words.append(_below_thousand(number))
    return " ".join(words)
