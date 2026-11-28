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

ORDINALS = [
    "first", "second", "third", "fourth", "fifth", "sixth",
    "seventh", "eighth", "ninth", "tenth", "eleventh", "twelfth",
]


def _gift_line(day):
    gifts = [GIFTS[i] for i in range(day - 1, -1, -1)]
    if len(gifts) == 1:
        return gifts[0]
    if len(gifts) == 2:
        return f"{gifts[0]}, {gifts[1]}"
    return ", ".join(gifts[:-1]) + ", and " + gifts[-1]


def _verse(day):
    return (
        f"On the {ORDINALS[day - 1]} day of Christmas my true love gave to me: "
        f"{_gift_line(day)}."
    )


def recite(start_verse, end_verse):
    lines = []
    for day in range(start_verse, end_verse + 1):
        if lines:
            lines.append("")
        lines.append(_verse(day))
    return lines
