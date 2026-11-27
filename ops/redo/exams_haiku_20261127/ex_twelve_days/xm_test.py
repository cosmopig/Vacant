"""Acceptance tests for the Twelve Days of Christmas exercise.

The expected verses below are copied verbatim from the exercise's lyrics.
The helper normalises the return value to a list of non-empty lines, so
either a list of verses or a single newline-separated string is accepted.
"""

from twelve_days import recite


VERSES = [
    "On the first day of Christmas my true love gave to me: a Partridge in a Pear Tree.",
    "On the second day of Christmas my true love gave to me: two Turtle Doves, and a Partridge in a Pear Tree.",
    "On the third day of Christmas my true love gave to me: three French Hens, two Turtle Doves, and a Partridge in a Pear Tree.",
    "On the fourth day of Christmas my true love gave to me: four Calling Birds, three French Hens, two Turtle Doves, and a Partridge in a Pear Tree.",
    "On the fifth day of Christmas my true love gave to me: five Gold Rings, four Calling Birds, three French Hens, two Turtle Doves, and a Partridge in a Pear Tree.",
    "On the sixth day of Christmas my true love gave to me: six Geese-a-Laying, five Gold Rings, four Calling Birds, three French Hens, two Turtle Doves, and a Partridge in a Pear Tree.",
    "On the seventh day of Christmas my true love gave to me: seven Swans-a-Swimming, six Geese-a-Laying, five Gold Rings, four Calling Birds, three French Hens, two Turtle Doves, and a Partridge in a Pear Tree.",
    "On the eighth day of Christmas my true love gave to me: eight Maids-a-Milking, seven Swans-a-Swimming, six Geese-a-Laying, five Gold Rings, four Calling Birds, three French Hens, two Turtle Doves, and a Partridge in a Pear Tree.",
    "On the ninth day of Christmas my true love gave to me: nine Ladies Dancing, eight Maids-a-Milking, seven Swans-a-Swimming, six Geese-a-Laying, five Gold Rings, four Calling Birds, three French Hens, two Turtle Doves, and a Partridge in a Pear Tree.",
    "On the tenth day of Christmas my true love gave to me: ten Lords-a-Leaping, nine Ladies Dancing, eight Maids-a-Milking, seven Swans-a-Swimming, six Geese-a-Laying, five Gold Rings, four Calling Birds, three French Hens, two Turtle Doves, and a Partridge in a Pear Tree.",
    "On the eleventh day of Christmas my true love gave to me: eleven Pipers Piping, ten Lords-a-Leaping, nine Ladies Dancing, eight Maids-a-Milking, seven Swans-a-Swimming, six Geese-a-Laying, five Gold Rings, four Calling Birds, three French Hens, two Turtle Doves, and a Partridge in a Pear Tree.",
    "On the twelfth day of Christmas my true love gave to me: twelve Drummers Drumming, eleven Pipers Piping, ten Lords-a-Leaping, nine Ladies Dancing, eight Maids-a-Milking, seven Swans-a-Swimming, six Geese-a-Laying, five Gold Rings, four Calling Birds, three French Hens, two Turtle Doves, and a Partridge in a Pear Tree.",
]


def _verse_lines(result):
    """Normalise a recite() result to a list of non-empty, stripped lines."""
    if isinstance(result, str):
        text = result
    else:
        text = "\n".join(str(item) for item in result)
    return [line.strip() for line in text.splitlines() if line.strip()]


def test_first_verse_alone():
    assert _verse_lines(recite(1, 1)) == [VERSES[0]]


def test_second_verse_alone():
    assert _verse_lines(recite(2, 2)) == [VERSES[1]]


def test_middle_verses_alone():
    assert _verse_lines(recite(4, 4)) == [VERSES[3]]
    assert _verse_lines(recite(8, 8)) == [VERSES[7]]


def test_last_verse_alone():
    assert _verse_lines(recite(12, 12)) == [VERSES[11]]


def test_first_two_verses():
    assert _verse_lines(recite(1, 2)) == VERSES[0:2]


def test_first_three_verses_are_cumulative():
    assert _verse_lines(recite(1, 3)) == VERSES[0:3]


def test_range_in_the_middle():
    assert _verse_lines(recite(6, 8)) == VERSES[5:8]


def test_range_to_the_end():
    assert _verse_lines(recite(10, 12)) == VERSES[9:12]


def test_full_song():
    assert _verse_lines(recite(1, 12)) == VERSES
