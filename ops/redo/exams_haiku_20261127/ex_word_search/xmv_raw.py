"""Acceptance tests for the word search exercise.

Assumed conventions (the requirements text does not state them, so they follow
the exercise's own example):
  * WordSearch receives the puzzle as a list of row strings.
  * Point(x, y) uses 1-indexed coordinates: x is the column (left to right) and
    y is the row (top to bottom), so the top-left letter is Point(1, 1).
  * search(word) returns a pair (first_letter_location, last_letter_location).
"""
from word_search import Point, WordSearch

PUZZLE_ROWS = [
    "jefblpepre",
    "camdcimgtc",
    "oivokprjsm",
    "pbwasqroua",
    "rixilelhrs",
    "wolcqlirpc",
    "screeaumgr",
    "alxhpburyi",
    "jalaycalmp",
    "clojurermt",
]


def _puzzle():
    return WordSearch(PUZZLE_ROWS)


def test_horizontal_left_to_right():
    puzzle = _puzzle()
    start, end = puzzle.search("clojure")
    # SRC: "Words can be hidden in all kinds of directions: left-to-right, right-to-left, vertical and diagonal."
    assert start == Point(1, 10)
    # SRC: "Given a puzzle and a list of words return the location of the first and last letter of each word."
    assert end == Point(7, 10)


def test_horizontal_right_to_left():
    puzzle = _puzzle()
    start, end = puzzle.search("elixir")
    # SRC: "Words can be hidden in all kinds of directions: left-to-right, right-to-left, vertical and diagonal."
    assert start == Point(6, 5)
    # SRC: "Given a puzzle and a list of words return the location of the first and last letter of each word."
    assert end == Point(1, 5)


def test_vertical_top_to_bottom_full_height():
    puzzle = _puzzle()
    start, end = puzzle.search("ecmascript")
    # SRC: "Words can be hidden in all kinds of directions: left-to-right, right-to-left, vertical and diagonal."
    assert start == Point(10, 1)
    # SRC: "Given a puzzle and a list of words return the location of the first and last letter of each word."
    assert end == Point(10, 10)


def test_diagonal_down_left():
    puzzle = _puzzle()
    start, end = puzzle.search("ruby")
    # SRC: "Words can be hidden in all kinds of directions: left-to-right, right-to-left, vertical and diagonal."
    assert start == Point(8, 6)
    # SRC: "There are several programming languages hidden in the above square."
    assert end == Point(5, 9)
