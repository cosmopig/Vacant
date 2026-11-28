"""Acceptance tests for the word search exercise.

Coordinates: a location is (x, y), where x is the column index and y is the
row index, both counted from 0 at the top-left corner of the puzzle. The
puzzle is a list of equal-length rows of letters.
"""
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


def _xy(loc):
    """Return (x, y) from a location given as an object with .x/.y or a 2-sequence."""
    if hasattr(loc, "x") and hasattr(loc, "y"):
        return (loc.x, loc.y)
    x, y = loc
    return (x, y)


def _span(result):
    """Return (first, last) as plain (x, y) tuples, asserting the overall shape."""
    assert result is not None, "word expected to be found but search returned None"
    assert len(result) == 2, "expected a pair of locations (first letter, last letter)"
    return (_xy(result[0]), _xy(result[1]))


def test_input_square_of_letters_is_accepted():
    """REQ: "In word search puzzles you get a square of letters and have to find specific words in them."
    A square puzzle given as rows of letters can be constructed and searched
    for a word that is hidden in it without error."""
    ws = WordSearch(PUZZLE)
    assert ws.search("ruby") is not None


def test_result_is_pair_of_integer_locations():
    """REQ: "Given a puzzle and a list of words return the location of the first and last letter of each word."
    A found word yields exactly two locations (first letter, last letter), each
    with integer x and y coordinates."""
    ws = WordSearch(PUZZLE)
    first, last = _span(ws.search("clojure"))
    for x, y in (first, last):
        assert isinstance(x, int) and isinstance(y, int)


def test_example_horizontal_left_to_right():
    """REQ: "Words can be hidden in all kinds of directions: left-to-right, right-to-left, vertical and diagonal."
    In the example square the bottom row reads "clojurermt", so "clojure" runs
    left-to-right from column 0 to column 6 of row 9."""
    ws = WordSearch(PUZZLE)
    assert _span(ws.search("clojure")) == ((0, 9), (6, 9))


def test_example_horizontal_right_to_left():
    """REQ: "Words can be hidden in all kinds of directions: left-to-right, right-to-left, vertical and diagonal."
    Row 4 is "rixilelhrs"; reading it right-to-left from column 5 gives "elixir"
    ending at column 0, so the span is (5,4) to (0,4)."""
    ws = WordSearch(PUZZLE)
    assert _span(ws.search("elixir")) == ((5, 4), (0, 4))


def test_example_vertical_top_to_bottom():
    """REQ: "Words can be hidden in all kinds of directions: left-to-right, right-to-left, vertical and diagonal."
    Column 0 reads c, o, p in rows 1, 2, 3, so "cop" runs top-to-bottom from
    (0,1) to (0,3)."""
    ws = WordSearch(PUZZLE)
    assert _span(ws.search("cop")) == ((0, 1), (0, 3))


def test_example_vertical_bottom_to_top():
    """REQ: "Words can be hidden in all kinds of directions: left-to-right, right-to-left, vertical and diagonal."
    Column 5 reads b, a, l in rows 7, 6, 5, so "bal" runs bottom-to-top from
    (5,7) to (5,5)."""
    ws = WordSearch(PUZZLE)
    assert _span(ws.search("bal")) == ((5, 7), (5, 5))


def test_example_diagonal_down_right():
    """REQ: "Words can be hidden in all kinds of directions: left-to-right, right-to-left, vertical and diagonal."
    Starting at (0,3) and stepping down-right gives p, i, l, e at (0,3), (1,4),
    (2,5), (3,6), so "pile" spans (0,3) to (3,6)."""
    ws = WordSearch(PUZZLE)
    assert _span(ws.search("pile")) == ((0, 3), (3, 6))


def test_example_diagonal_down_left():
    """REQ: "Words can be hidden in all kinds of directions: left-to-right, right-to-left, vertical and diagonal."
    Starting at (7,5) and stepping down-left gives r, u, b, y at (7,5), (6,6),
    (5,7), (4,8), so "ruby" spans (7,5) to (4,8)."""
    ws = WordSearch(PUZZLE)
    assert _span(ws.search("ruby")) == ((7, 5), (4, 8))


def test_example_diagonal_up_right():
    """REQ: "Words can be hidden in all kinds of directions: left-to-right, right-to-left, vertical and diagonal."
    Starting at (4,8) and stepping up-right gives y, b, u, r at (4,8), (5,7),
    (6,6), (7,5), so "ybur" spans (4,8) to (7,5)."""
    ws = WordSearch(PUZZLE)
    assert _span(ws.search("ybur")) == ((4, 8), (7, 5))


def test_example_diagonal_up_left():
    """REQ: "Words can be hidden in all kinds of directions: left-to-right, right-to-left, vertical and diagonal."
    Starting at (7,9) and stepping up-left gives r, a, b at (7,9), (6,8), (5,7),
    so "rab" spans (7,9) to (5,7)."""
    ws = WordSearch(PUZZLE)
    assert _span(ws.search("rab")) == ((7, 9), (5, 7))


def test_span_is_straight_line_spelling_word():
    """REQ: "Words can be hidden in all kinds of directions: left-to-right, right-to-left, vertical and diagonal."
    For each word, the first and last letters are on one horizontal, vertical or
    diagonal line, the line covers exactly len(word) cells, all coordinates lie
    inside the square, and reading the puzzle along that line from first to last
    gives the word."""
    ws = WordSearch(PUZZLE)
    size = len(PUZZLE)
    for word in ["clojure", "elixir", "cop", "bal", "ruby", "pile", "ybur", "rab"]:
        first, last = _span(ws.search(word))
        (x0, y0), (x1, y1) = first, last
        for x, y in (first, last):
            assert 0 <= x < size and 0 <= y < size, f"{word}: location out of the square"
        dx, dy = x1 - x0, y1 - y0
        assert dx == 0 or dy == 0 or abs(dx) == abs(dy), f"{word}: span is not a straight line"
        steps = max(abs(dx), abs(dy))
        assert steps == len(word) - 1, f"{word}: span does not cover exactly len(word) letters"
        sx = (dx > 0) - (dx < 0)
        sy = (dy > 0) - (dy < 0)
        letters = "".join(PUZZLE[y0 + i * sy][x0 + i * sx] for i in range(steps + 1))
        assert letters == word, f"{word}: letters along the span read {letters!r}"


def test_reversed_word_swaps_first_and_last_location():
    """REQ: "Given a puzzle and a list of words return the location of the first and last letter of each word."
    Row 4 reads "rixilelhrs", so "rixile" runs left-to-right from (0,4) to (5,4).
    The first location is the first letter read, which is the opposite of the
    location returned for "elixir" in the same row."""
    ws = WordSearch(PUZZLE)
    assert _span(ws.search("rixile")) == ((0, 4), (5, 4))


def test_several_words_searched_on_one_puzzle():
    """REQ: "Given a puzzle and a list of words return the location of the first and last letter of each word."
    One puzzle object can be searched for several words and each result is the
    correct location for its word."""
    ws = WordSearch(PUZZLE)
    assert _span(ws.search("clojure")) == ((0, 9), (6, 9))
    assert _span(ws.search("elixir")) == ((5, 4), (0, 4))
    assert _span(ws.search("cop")) == ((0, 1), (0, 3))
    assert _span(ws.search("ruby")) == ((7, 5), (4, 8))
    assert _span(ws.search("pile")) == ((0, 3), (3, 6))


def test_repeated_search_gives_same_location():
    """REQ: "Given a puzzle and a list of words return the location of the first and last letter of each word."
    Searching for the same word twice on the same puzzle gives the same location
    both times."""
    ws = WordSearch(PUZZLE)
    assert _span(ws.search("ruby")) == _span(ws.search("ruby"))


def test_single_cell_square_boundary():
    """REQ: "In word search puzzles you get a square of letters and have to find specific words in them."
    The smallest square is a single letter. Searching for that letter gives
    the same location as both its first and last letter, (0,0)."""
    ws = WordSearch(["a"])
    assert _span(ws.search("a")) == ((0, 0), (0, 0))


def test_two_by_two_square_all_directions():
    """REQ: "Words can be hidden in all kinds of directions: left-to-right, right-to-left, vertical and diagonal."
    In the square ["ab", "cd"], "ab" runs left-to-right, "ac" runs top-to-bottom,
    "ad" runs down-right and "bc" runs down-left."""
    ws = WordSearch(["ab", "cd"])
    assert _span(ws.search("ab")) == ((0, 0), (1, 0))
    assert _span(ws.search("ac")) == ((0, 0), (0, 1))
    assert _span(ws.search("ad")) == ((0, 0), (1, 1))
    assert _span(ws.search("bc")) == ((1, 0), (0, 1))
