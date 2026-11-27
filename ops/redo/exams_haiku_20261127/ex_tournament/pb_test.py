"""Acceptance tests for the football competition tally.

Each check function covers one property taken from the requirements text.
Expected values were worked out by hand from the requirements text.
"""

from tournament import tally

HEADER_CELLS = ["Team", "MP", "W", "D", "L", "P"]
NAME_WIDTH = 31


def _example_rows():
    """Return a fresh copy of the example input from the requirements text."""
    return [
        "Allegoric Alaskans;Blithering Badgers;win",
        "Devastating Donkeys;Courageous Californians;draw",
        "Devastating Donkeys;Allegoric Alaskans;win",
        "Courageous Californians;Blithering Badgers;loss",
        "Blithering Badgers;Devastating Donkeys;loss",
        "Allegoric Alaskans;Courageous Californians;win",
    ]


def _example_expected_lines():
    """Return the expected output lines for the example input, from the requirements text."""

    def row(name, nums):
        mp, w, d, l, p = nums
        return f"{name:<{NAME_WIDTH}}| {mp:>2} | {w:>2} | {d:>2} | {l:>2} | {p:>2}"

    header = (
        f"{'Team':<{NAME_WIDTH}}| {'MP':>2} | {'W':>2} | {'D':>2} | {'L':>2} | {'P':>2}"
    )
    return [
        header,
        row("Devastating Donkeys", (3, 2, 1, 0, 7)),
        row("Allegoric Alaskans", (3, 2, 0, 1, 6)),
        row("Blithering Badgers", (3, 1, 0, 2, 3)),
        row("Courageous Californians", (3, 0, 1, 2, 1)),
    ]


def _as_lines(result):
    """Normalise the output of tally to a list of text lines (str or list of str accepted)."""
    if isinstance(result, str):
        return result.splitlines()
    assert isinstance(result, (list, tuple)), (
        f"tally must return a str or a list of str, got {type(result).__name__}"
    )
    assert all(isinstance(x, str) for x in result), "every output line must be a str"
    return "\n".join(result).splitlines()


def _parse(result):
    """Return (lines, rows) where rows is a list of (team_name, [mp, w, d, l, p])."""
    lines = _as_lines(result)
    assert lines, "output must contain at least the header line"
    rows = []
    for line in lines[1:]:
        if not line.strip():
            continue
        cells = line.split("|")
        assert len(cells) == 6, f"row must have 6 '|'-separated cells: {line!r}"
        name = cells[0].strip()
        nums = [int(c) for c in cells[1:]]
        rows.append((name, nums))
    return lines, rows


def test_output_is_text_lines_with_header_first():
    """REQ: "create a file with a table like this" """
    lines, rows = _parse(tally(_example_rows()))
    assert lines[0].startswith("Team")
    assert len(rows) == 4
    assert all("|" in line for line in lines)


def test_header_columns_in_order():
    """REQ: "MP: Matches Played" """
    lines = _as_lines(tally(_example_rows()))
    cells = [c.strip() for c in lines[0].split("|")]
    assert cells == HEADER_CELLS


def test_accepts_list_of_semicolon_separated_rows():
    """REQ: "Your tallying program will receive input that looks like:" """
    _, rows = _parse(tally(["Alpha;Beta;win"]))
    names = sorted(name for name, _ in rows)
    assert names == ["Alpha", "Beta"]


def test_example_table_exact():
    """REQ: "create a file with a table like this" """
    assert _as_lines(tally(_example_rows())) == _example_expected_lines()


def test_matches_played_is_won_plus_drawn_plus_lost():
    """REQ: "MP: Matches Played" """
    _, rows = _parse(tally(_example_rows()))
    for name, nums in rows:
        mp, w, d, l, _p = nums
        assert mp == w + d + l, f"{name}: MP {mp} != W+D+L {w + d + l}"


def test_win_earns_three_points():
    """REQ: "A win earns a team 3 points." """
    _, rows = _parse(tally(["Alpha;Beta;win"]))
    table = dict(rows)
    assert table["Alpha"] == [1, 1, 0, 0, 3]


def test_draw_earns_one_point():
    """REQ: "A draw earns 1." """
    _, rows = _parse(tally(["Alpha;Beta;draw"]))
    table = dict(rows)
    assert table["Alpha"] == [1, 0, 1, 0, 1]
    assert table["Beta"] == [1, 0, 1, 0, 1]


def test_loss_earns_zero_points():
    """REQ: "A loss earns 0." """
    _, rows = _parse(tally(["Alpha;Beta;win"]))
    table = dict(rows)
    assert table["Beta"] == [1, 0, 0, 1, 0]


def test_result_refers_to_first_team_listed():
    """REQ: "The result of the match refers to the first team listed." """
    _, rows = _parse(tally(["Alpha;Beta;loss"]))
    table = dict(rows)
    assert table["Beta"] == [1, 1, 0, 0, 3]
    assert table["Alpha"] == [1, 0, 0, 1, 0]


def test_ordered_by_points_descending():
    """REQ: "The outcome is ordered by points, descending." """
    _, rows = _parse(tally(_example_rows()))
    points = [nums[4] for _, nums in rows]
    assert points == sorted(points, reverse=True)


def test_tie_on_points_ordered_alphabetically():
    """REQ: "In case of a tie, teams are ordered alphabetically." """
    _, rows = _parse(tally(["Bravo;Charlie;win", "Zulu;Yankee;win"]))
    names = [name for name, _ in rows]
    assert names == ["Bravo", "Zulu", "Charlie", "Yankee"]


def test_each_team_appears_once():
    """REQ: "Based on an input file containing which team played against which and what the outcome was" """
    _, rows = _parse(tally(_example_rows()))
    names = [name for name, _ in rows]
    assert len(names) == len(set(names)) == 4
    assert set(names) == {
        "Devastating Donkeys",
        "Allegoric Alaskans",
        "Blithering Badgers",
        "Courageous Californians",
    }


def test_each_match_counts_for_both_teams():
    """REQ: "means that the Allegoric Alaskans beat the Blithering Badgers." """
    rows_in = _example_rows()
    _, rows = _parse(tally(rows_in))
    total_mp = sum(nums[0] for _, nums in rows)
    assert total_mp == 2 * len(rows_in)


def test_total_wins_equal_total_losses():
    """REQ: "means that the Allegoric Alaskans beat the Blithering Badgers." """
    _, rows = _parse(tally(_example_rows()))
    total_w = sum(nums[1] for _, nums in rows)
    total_l = sum(nums[3] for _, nums in rows)
    assert total_w == total_l


def test_empty_input_gives_header_only():
    """REQ: "create a file with a table like this" """
    lines = _as_lines(tally([]))
    assert len(lines) == 1
    assert [c.strip() for c in lines[0].split("|")] == HEADER_CELLS


def test_result_independent_of_match_order():
    """REQ: "Based on an input file containing which team played against which and what the outcome was" """
    forward = _as_lines(tally(_example_rows()))
    backward = _as_lines(tally(list(reversed(_example_rows()))))
    assert forward == backward
