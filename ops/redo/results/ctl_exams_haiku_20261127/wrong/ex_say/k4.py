ONES = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
        "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
        "seventeen", "eighteen", "nineteen"]
TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]
SCALES = ["", "thousand", "million", "billion", "trillion"]


def _below_hundred(n):
    if n < 20:
        return ONES[n]
    tens, ones = divmod(n, 10)
    return TENS[tens] if ones == 0 else f"{TENS[tens]}-{ONES[ones]}"


def _below_thousand(n):
    hundreds, rest = divmod(n, 100)
    parts = []
    if hundreds:
        parts.append(f"{ONES[hundreds]} hundred")
    if rest:
        parts.append(_below_hundred(rest))
    return " ".join(parts)


def say(number):
    if number < 0 or number > 10**12:
        raise ValueError("input out of range")
    if number == 0:
        return "zero"
    chunks = []
    scale = 0
    while number:
        number, chunk = divmod(number, 1000)
        if chunk:
            words = _below_thousand(chunk)
            if SCALES[scale]:
                words = f"{words} {SCALES[scale]}"
            chunks.append(words)
        scale += 1
    return " ".join(reversed(chunks))
