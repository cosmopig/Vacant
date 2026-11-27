ORDINALS = [
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


def _verse(day):
    gifts = [GIFTS[i] for i in range(day - 1, -1, -1)]
    if day > 2:
        gifts[-1] = "and " + gifts[-1]
    listing = ", ".join(gifts)
    return (
        f"On the {ORDINALS[day - 1]} day of Christmas "
        f"my true love gave to me: {listing}."
    )


def recite(start_verse, end_verse):
    return [_verse(day) for day in range(start_verse, end_verse + 1)]
