from word_search import WordSearch

PUZZLE = [
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

# The requirements do not fix the coordinate convention, so a result is accepted
# if both the start and end points match one consistent convention:
# (x, y) = (column, row) or (row, column), each 0-indexed or 1-indexed.
# Expected positions below are given as (row, column), 0-indexed.
CONVENTIONS = [
    lambda row, col: (col + 1, row + 1),
    lambda row, col: (col, row),
    lambda row, col: (row + 1, col + 1),
    lambda row, col: (row, col),
]


def _xy(point):
    return (point.x, point.y)


def _matches(result, start_rc, end_rc):
    start, end = result[0], result[1]
    return any(
        _xy(start) == conv(*start_rc) and _xy(end) == conv(*end_rc)
        for conv in CONVENTIONS
    )


def test_horizontal_left_to_right_on_bottom_edge():
    # "clojure" in the bottom row, columns 0..6
    ws = WordSearch(PUZZLE)
    assert _matches(ws.search("clojure"), (9, 0), (9, 6))


def test_horizontal_right_to_left():
    # "elixir" reads right-to-left in row 4, columns 5..0
    ws = WordSearch(PUZZLE)
    assert _matches(ws.search("elixir"), (4, 5), (4, 0))


def test_horizontal_word_in_middle_of_grid():
    # "bury" in row 7, columns 5..8
    ws = WordSearch(PUZZLE)
    assert _matches(ws.search("bury"), (7, 5), (7, 8))


def test_vertical_bottom_to_top():
    # "rust" reads upward in column 8, from row 4 to row 1
    ws = WordSearch(PUZZLE)
    assert _matches(ws.search("rust"), (4, 8), (1, 8))


def test_vertical_top_to_bottom():
    # "tsur" reads downward in column 8, from row 1 to row 4
    ws = WordSearch(PUZZLE)
    assert _matches(ws.search("tsur"), (1, 8), (4, 8))


def test_diagonal_down_right_starting_at_top_left_corner():
    # "java" runs from (0,0) down-right to (3,3)
    ws = WordSearch(PUZZLE)
    assert _matches(ws.search("java"), (0, 0), (3, 3))


def test_diagonal_up_left_ending_at_top_left_corner():
    # "avaj" runs from (3,3) up-left to (0,0)
    ws = WordSearch(PUZZLE)
    assert _matches(ws.search("avaj"), (3, 3), (0, 0))


def test_diagonal_down_left():
    # "ruby" runs from (5,7) down-left to (8,4)
    ws = WordSearch(PUZZLE)
    assert _matches(ws.search("ruby"), (5, 7), (8, 4))


def test_reversed_word_swaps_start_and_end():
    ws = WordSearch(PUZZLE)
    forward = ws.search("ruby")
    backward = ws.search("ybur")
    assert _xy(backward[0]) == _xy(forward[1])
    assert _xy(backward[1]) == _xy(forward[0])


def test_multiple_searches_on_same_puzzle_are_independent():
    ws = WordSearch(PUZZLE)
    first = ws.search("clojure")
    second = ws.search("elixir")
    third = ws.search("java")
    assert _matches(first, (9, 0), (9, 6))
    assert _matches(second, (4, 5), (4, 0))
    assert _matches(third, (0, 0), (3, 3))
