ONES = ["", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
        "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
        "seventeen", "eighteen", "nineteen"]
TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]
SCALES = [(10 ** 9, "billion"), (10 ** 6, "million"), (10 ** 3, "thousand")]


def _below_100(n):
    if n < 20:
        return ONES[n]
    tens, ones = divmod(n, 10)
    if ones == 0:
        return TENS[tens]
    return f"{TENS[tens]} {ONES[ones]}"


def _below_1000(n):
    hundreds, rest = divmod(n, 100)
    parts = []
    if hundreds:
        parts.append(f"{ONES[hundreds]} hundred")
    if rest:
        parts.append(_below_100(rest))
    return " ".join(parts)


def say(number):
    if number < 0 or number > 999_999_999_999:
        raise ValueError("input out of range")
    if number == 0:
        return "zero"
    parts = []
    for value, name in SCALES:
        chunk, number = divmod(number, value)
        if chunk:
            parts.append(f"{_below_1000(chunk)} {name}")
    if number:
        parts.append(_below_1000(number))
    return " ".join(parts)
