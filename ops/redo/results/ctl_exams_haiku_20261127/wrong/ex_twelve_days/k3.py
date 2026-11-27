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


def _gifts_for(day):
    items = GIFTS[:day][::-1]
    if day == 1:
        return items[0]
    return ", ".join(items[:-1]) + ", and " + items[-1]


def _verse(day):
    return (
        f"On the {ORDINALS[day - 1]} day of Christmas my true love gave to me: "
        f"{_gifts_for(day)}."
    )


def recite(start_verse, end_verse):
    return [_verse(day) for day in range(end_verse, start_verse - 1, -1)]
