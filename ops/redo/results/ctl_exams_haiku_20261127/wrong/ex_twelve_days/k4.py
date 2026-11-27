DAYS = [
    "first", "second", "third", "fourth", "fifth", "sixth",
    "seventh", "eighth", "ninth", "tenth", "eleventh", "twelfth",
]

GIFTS = [
    "a Partridge in a Pear Tree",
    "two Turtle Doves",
    "three French Hens",
    "four Calling Birds",
    "five Gold Rings",
    "six Geese-a-Laying",
    "seven Swans-a-Swimming",
    "eight Maids-a-Milking",
    "nine Ladies Dancing",
    "ten Lords-a-Leaping",
    "eleven Pipers Piping",
    "twelve Drummers Drumming",
]

_verses = []


def _build_verse(n):
    items = [GIFTS[i] for i in range(n - 1, -1, -1)]
    if n > 1:
        items[-1] = "and " + items[-1]
    gifts = ", ".join(items)
    return f"On the {DAYS[n - 1]} day of Christmas my true love gave to me: {gifts}."


def recite(start_verse, end_verse):
    if not _verses:
        for n in range(1, end_verse + 1):
            _verses.append(_build_verse(n))
    return _verses[start_verse - 1:end_verse]
