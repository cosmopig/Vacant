"""Acceptance tests for the 'The Twelve Days of Christmas' exercise."""

import pytest

from twelve_days import recite


ORDINALS = (
    "first", "second", "third", "fourth", "fifth", "sixth",
    "seventh", "eighth", "ninth", "tenth", "eleventh", "twelfth",
)

EXPECTED = (
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
)


def _verses(result):
    """Return the non-blank lines of the result as a list of verse strings.

    Accepts either a single string (verses separated by blank lines) or a
    sequence of strings (one verse per element). Pure helper, no state.
    """
    if isinstance(result, str):
        pieces = result.split("\n")
    else:
        assert isinstance(result, (list, tuple)), f"unexpected result type: {type(result)!r}"
        pieces = []
        for item in result:
            assert isinstance(item, str), f"non-string element: {item!r}"
            pieces.extend(item.split("\n"))
    return [p.strip() for p in pieces if p.strip()]


def _body(verse):
    """Return the text after 'gave to me: ' in a verse."""
    return verse.split("me: ", 1)[1]


def _norm(body):
    """Remove the 'and' before the final gift so bodies can be compared as lists."""
    return body.replace(", and ", ", ")


def test_recite_returns_text_or_sequence_with_twelve_verses():
    '''REQ: "Your task in this exercise is to write code that returns the lyrics of the song" - the result is text (or a sequence of verse strings) containing all twelve verses.'''
    result = recite(1, 12)
    assert isinstance(result, (str, list, tuple))
    assert len(_verses(result)) == 12


def test_first_verse_exact():
    '''REQ: "On the first day of Christmas my true love gave to me: a Partridge in a Pear Tree." - recite(1, 1) returns exactly this verse.'''
    assert _verses(recite(1, 1)) == [EXPECTED[0]]


def test_second_verse_example():
    '''REQ: "On the second day of Christmas my true love gave to me: two Turtle Doves, and a Partridge in a Pear Tree." - recite(2, 2) returns exactly this verse.'''
    assert _verses(recite(2, 2)) == [EXPECTED[1]]


def test_sixth_verse_example():
    '''REQ: "On the sixth day of Christmas my true love gave to me: six Geese-a-Laying, five Gold Rings, four Calling Birds, three French Hens, two Turtle Doves, and a Partridge in a Pear Tree." - recite(6, 6) returns exactly this verse.'''
    assert _verses(recite(6, 6)) == [EXPECTED[5]]


def test_twelfth_verse_boundary():
    '''REQ: "On the twelfth day of Christmas my true love gave to me: twelve Drummers Drumming, eleven Pipers Piping, ten Lords-a-Leaping, nine Ladies Dancing, eight Maids-a-Milking, seven Swans-a-Swimming, six Geese-a-Laying, five Gold Rings, four Calling Birds, three French Hens, two Turtle Doves, and a Partridge in a Pear Tree." - recite(12, 12) returns only the last verse.'''
    assert _verses(recite(12, 12)) == [EXPECTED[11]]


def test_full_song_matches_exactly():
    '''REQ: "The lyrics your code returns should _exactly_ match the full song text shown below." - recite(1, 12) yields all twelve verses, in order, with exact text.'''
    assert _verses(recite(1, 12)) == list(EXPECTED)


def test_string_output_separates_verses_with_blank_line():
    '''REQ: "The lyrics your code returns should _exactly_ match the full song text shown below." - in the lyrics block each verse is followed by one blank line before the next verse.'''
    result = recite(1, 12)
    if not isinstance(result, str):
        pytest.skip("verse layout only applies to string output")
    assert result.strip("\n") == "\n\n".join(EXPECTED)


def test_range_is_inclusive_of_both_ends():
    '''REQ: "Your task in this exercise is to write code that returns the lyrics of the song" - recite(start_verse, end_verse) returns verses start_verse through end_verse inclusive, e.g. recite(3, 5) gives verses 3, 4 and 5.'''
    assert _verses(recite(3, 5)) == list(EXPECTED[2:5])


def test_verse_count_equals_range_size():
    '''REQ: "Your task in this exercise is to write code that returns the lyrics of the song" - the number of verses returned equals end_verse minus start_verse plus one.'''
    for start, end in [(1, 1), (5, 8), (10, 12), (1, 12)]:
        assert len(_verses(recite(start, end))) == end - start + 1, (start, end)


def test_range_equals_concatenation_of_single_verses():
    '''REQ: "Each subsequent verse of the song builds on the previous verse." - the full song is the in-order concatenation of each single verse returned by recite(n, n).'''
    combined = []
    for n in range(1, 13):
        combined.extend(_verses(recite(n, n)))
    assert combined == _verses(recite(1, 12))


def test_each_verse_has_correct_day_header():
    '''REQ: "On the second day of Christmas my true love gave to me: two Turtle Doves, and a Partridge in a Pear Tree." - verse n begins with "On the <ordinal> day of Christmas my true love gave to me: " for its own day.'''
    verses = _verses(recite(1, 12))
    for n, verse in enumerate(verses, start=1):
        expected_header = f"On the {ORDINALS[n - 1]} day of Christmas my true love gave to me: "
        assert verse.startswith(expected_header), (n, verse)


def test_each_verse_ends_with_partridge_line():
    '''REQ: "On the first day of Christmas my true love gave to me: a Partridge in a Pear Tree." - every verse of the song ends with "a Partridge in a Pear Tree."'''
    for verse in _verses(recite(1, 12)):
        assert verse.endswith("a Partridge in a Pear Tree."), verse


def test_each_verse_builds_on_previous_verse():
    '''REQ: "Each subsequent verse of the song builds on the previous verse." - for each verse after the first, its gift list is the previous verse's gift list with one new gift prepended.'''
    verses = _verses(recite(1, 12))
    for n in range(2, 13):
        prev_norm = _norm(_body(verses[n - 2]))
        cur_norm = _norm(_body(verses[n - 1]))
        assert cur_norm.endswith(prev_norm), (n, verses[n - 1])
        prefix = cur_norm[: len(cur_norm) - len(prev_norm)]
        assert prefix.endswith(", "), (n, verses[n - 1])
        assert len(prefix) > 2, (n, verses[n - 1])
