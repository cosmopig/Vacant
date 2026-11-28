"""Acceptance tests for the "The Twelve Days of Christmas" exercise.

Each verse is compared as one line of text. Output from recite() may be a
string or a list of verse strings. Blank lines between verses are ignored.
"""

from twelve_days import recite


VERSE_1 = "On the first day of Christmas my true love gave to me: a Partridge in a Pear Tree."
VERSE_2 = "On the second day of Christmas my true love gave to me: two Turtle Doves, and a Partridge in a Pear Tree."
VERSE_3 = "On the third day of Christmas my true love gave to me: three French Hens, two Turtle Doves, and a Partridge in a Pear Tree."
VERSE_4 = "On the fourth day of Christmas my true love gave to me: four Calling Birds, three French Hens, two Turtle Doves, and a Partridge in a Pear Tree."
VERSE_5 = "On the fifth day of Christmas my true love gave to me: five Gold Rings, four Calling Birds, three French Hens, two Turtle Doves, and a Partridge in a Pear Tree."
VERSE_6 = "On the sixth day of Christmas my true love gave to me: six Geese-a-Laying, five Gold Rings, four Calling Birds, three French Hens, two Turtle Doves, and a Partridge in a Pear Tree."
VERSE_7 = "On the seventh day of Christmas my true love gave to me: seven Swans-a-Swimming, six Geese-a-Laying, five Gold Rings, four Calling Birds, three French Hens, two Turtle Doves, and a Partridge in a Pear Tree."
VERSE_8 = "On the eighth day of Christmas my true love gave to me: eight Maids-a-Milking, seven Swans-a-Swimming, six Geese-a-Laying, five Gold Rings, four Calling Birds, three French Hens, two Turtle Doves, and a Partridge in a Pear Tree."
VERSE_9 = "On the ninth day of Christmas my true love gave to me: nine Ladies Dancing, eight Maids-a-Milking, seven Swans-a-Swimming, six Geese-a-Laying, five Gold Rings, four Calling Birds, three French Hens, two Turtle Doves, and a Partridge in a Pear Tree."
VERSE_10 = "On the tenth day of Christmas my true love gave to me: ten Lords-a-Leaping, nine Ladies Dancing, eight Maids-a-Milking, seven Swans-a-Swimming, six Geese-a-Laying, five Gold Rings, four Calling Birds, three French Hens, two Turtle Doves, and a Partridge in a Pear Tree."
VERSE_11 = "On the eleventh day of Christmas my true love gave to me: eleven Pipers Piping, ten Lords-a-Leaping, nine Ladies Dancing, eight Maids-a-Milking, seven Swans-a-Swimming, six Geese-a-Laying, five Gold Rings, four Calling Birds, three French Hens, two Turtle Doves, and a Partridge in a Pear Tree."
VERSE_12 = "On the twelfth day of Christmas my true love gave to me: twelve Drummers Drumming, eleven Pipers Piping, ten Lords-a-Leaping, nine Ladies Dancing, eight Maids-a-Milking, seven Swans-a-Swimming, six Geese-a-Laying, five Gold Rings, four Calling Birds, three French Hens, two Turtle Doves, and a Partridge in a Pear Tree."

FULL = [
    VERSE_1, VERSE_2, VERSE_3, VERSE_4, VERSE_5, VERSE_6,
    VERSE_7, VERSE_8, VERSE_9, VERSE_10, VERSE_11, VERSE_12,
]


def _verses(result):
    """Normalise recite() output into a list of non-empty verse lines."""
    if isinstance(result, str):
        text = result
    else:
        text = "\n".join(str(item) for item in result)
    return [line.strip() for line in text.splitlines() if line.strip()]


def test_first_verse_alone():
    # SRC: "On the first day of Christmas my true love gave to me: a Partridge in a Pear Tree."
    assert _verses(recite(1, 1)) == [VERSE_1]


def test_second_verse_alone():
    # SRC: "On the second day of Christmas my true love gave to me: two Turtle Doves, and a Partridge in a Pear Tree."
    assert _verses(recite(2, 2)) == [VERSE_2]


def test_fifth_verse_alone():
    # SRC: "On the fifth day of Christmas my true love gave to me: five Gold Rings, four Calling Birds, three French Hens, two Turtle Doves, and a Partridge in a Pear Tree."
    assert _verses(recite(5, 5)) == [VERSE_5]


def test_twelfth_verse_alone():
    # SRC: "On the twelfth day of Christmas my true love gave to me: twelve Drummers Drumming, eleven Pipers Piping, ten Lords-a-Leaping, nine Ladies Dancing, eight Maids-a-Milking, seven Swans-a-Swimming, six Geese-a-Laying, five Gold Rings, four Calling Birds, three French Hens, two Turtle Doves, and a Partridge in a Pear Tree."
    assert _verses(recite(12, 12)) == [VERSE_12]


def test_range_of_first_three_verses():
    # SRC: "Each subsequent verse of the song builds on the previous verse."
    assert _verses(recite(1, 3)) == [VERSE_1, VERSE_2, VERSE_3]


def test_range_of_middle_verses():
    # SRC: "Each subsequent verse of the song builds on the previous verse."
    assert _verses(recite(4, 6)) == [VERSE_4, VERSE_5, VERSE_6]


def test_range_of_last_verses():
    # SRC: "Each subsequent verse of the song builds on the previous verse."
    assert _verses(recite(10, 12)) == [VERSE_10, VERSE_11, VERSE_12]


def test_full_song():
    # SRC: "The lyrics your code returns should _exactly_ match the full song text shown below."
    assert _verses(recite(1, 12)) == FULL
