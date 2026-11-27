from flower_field import annotate


def test_example_board_is_annotated():
    garden = [
        " * * ",
        "  *  ",
        "  *  ",
        "     ",
    ]
    expected = [
        "1*3*1",
        "13*31",
        " 2*2 ",
        " 111 ",
    ]
    # SRC: "Which your code should transform into this:"
    assert annotate(garden) == expected


def test_empty_square_without_adjacent_flowers_stays_empty():
    garden = [
        "   ",
        "   ",
        "   ",
    ]
    # SRC: "If the empty square has no adjacent flowers, leave it empty."
    assert annotate(garden) == ["   ", "   ", "   "]


def test_board_of_only_flowers_is_unchanged():
    garden = [
        "***",
        "***",
    ]
    # SRC: "For each empty square, count the number of flowers adjacent to it (horizontally, vertically, diagonally)."
    assert annotate(garden) == ["***", "***"]


def test_single_empty_square_stays_empty():
    # SRC: "If the empty square has no adjacent flowers, leave it empty."
    assert annotate([" "]) == [" "]


def test_single_flower_square_is_unchanged():
    # SRC: "For each empty square, count the number of flowers adjacent to it (horizontally, vertically, diagonally)."
    assert annotate(["*"]) == ["*"]


def test_diagonal_neighbours_are_counted():
    garden = [
        "   ",
        " * ",
        "   ",
    ]
    expected = [
        "111",
        "1*1",
        "111",
    ]
    # SRC: "For each empty square, count the number of flowers adjacent to it (horizontally, vertically, diagonally)."
    assert annotate(garden) == expected


def test_empty_square_surrounded_by_flowers_counts_eight():
    garden = [
        "***",
        "* *",
        "***",
    ]
    expected = [
        "***",
        "*8*",
        "***",
    ]
    # SRC: "Otherwise replace it with the count of adjacent flowers."
    assert annotate(garden) == expected


def test_vertical_neighbours_are_counted():
    # SRC: "For each empty square, count the number of flowers adjacent to it (horizontally, vertically, diagonally)."
    assert annotate([" ", "*", " "]) == ["1", "*", "1"]


def test_horizontal_neighbours_are_counted():
    # SRC: "For each empty square, count the number of flowers adjacent to it (horizontally, vertically, diagonally)."
    assert annotate(["* *"]) == ["*2*"]


def test_mixed_zero_and_nonzero_counts_on_edge():
    garden = [
        "*  ",
        "   ",
        "   ",
    ]
    expected = [
        "*1 ",
        "11 ",
        "   ",
    ]
    # SRC: "If the empty square has no adjacent flowers, leave it empty."
    assert annotate(garden) == expected
