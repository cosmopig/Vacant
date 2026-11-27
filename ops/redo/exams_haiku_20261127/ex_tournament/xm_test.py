from tournament import tally

HEADER = f"{'Team':<31}|{'MP':>3} |{'W':>3} |{'D':>3} |{'L':>3} |{'P':>3}"


def row(name, played, won, drawn, lost, points):
    return f"{name:<31}|{played:>3} |{won:>3} |{drawn:>3} |{lost:>3} |{points:>3}"


def lines_of(result):
    if isinstance(result, str):
        raw = result.splitlines()
    else:
        raw = list(result)
    return [line.rstrip() for line in raw if line.strip()]


def test_example_from_requirements():
    rows = [
        "Allegoric Alaskans;Blithering Badgers;win",
        "Devastating Donkeys;Courageous Californians;draw",
        "Devastating Donkeys;Allegoric Alaskans;win",
        "Courageous Californians;Blithering Badgers;loss",
        "Blithering Badgers;Devastating Donkeys;loss",
        "Allegoric Alaskans;Courageous Californians;win",
    ]
    lines = lines_of(tally(rows))
    assert lines[0] == HEADER
    assert len(lines) == 5
    assert lines == [
        HEADER,
        row("Devastating Donkeys", 3, 2, 1, 0, 7),
        row("Allegoric Alaskans", 3, 2, 0, 1, 6),
        row("Blithering Badgers", 3, 1, 0, 2, 3),
        row("Courageous Californians", 3, 0, 1, 2, 1),
    ]


def test_single_win_gives_three_points():
    lines = lines_of(tally(["Alpha;Beta;win"]))
    assert lines == [
        HEADER,
        row("Alpha", 1, 1, 0, 0, 3),
        row("Beta", 1, 0, 0, 1, 0),
    ]


def test_loss_gives_winner_the_points():
    lines = lines_of(tally(["Alpha;Beta;loss"]))
    assert lines == [
        HEADER,
        row("Beta", 1, 1, 0, 0, 3),
        row("Alpha", 1, 0, 0, 1, 0),
    ]


def test_draw_gives_one_point_each_and_ties_sorted_alphabetically():
    lines = lines_of(tally(["Bravo;Alpha;draw"]))
    assert lines == [
        HEADER,
        row("Alpha", 1, 0, 1, 0, 1),
        row("Bravo", 1, 0, 1, 0, 1),
    ]


def test_points_order_overrides_alphabetical_order():
    lines = lines_of(tally(["Zeta;Alpha;win"]))
    assert lines == [
        HEADER,
        row("Zeta", 1, 1, 0, 0, 3),
        row("Alpha", 1, 0, 0, 1, 0),
    ]


def test_equal_points_sorted_alphabetically_regardless_of_matches_played():
    rows = [
        "Zulu;Mike;draw",
        "Zulu;Nancy;draw",
        "Zulu;Oscar;draw",
        "Alpha;Bravo;win",
    ]
    lines = lines_of(tally(rows))
    assert lines == [
        HEADER,
        row("Alpha", 1, 1, 0, 0, 3),
        row("Zulu", 3, 0, 3, 0, 3),
        row("Mike", 1, 0, 1, 0, 1),
        row("Nancy", 1, 0, 1, 0, 1),
        row("Oscar", 1, 0, 1, 0, 1),
        row("Bravo", 1, 0, 0, 1, 0),
    ]


def test_match_order_does_not_change_table():
    rows = [
        "Allegoric Alaskans;Blithering Badgers;win",
        "Devastating Donkeys;Courageous Californians;draw",
        "Devastating Donkeys;Allegoric Alaskans;win",
        "Courageous Californians;Blithering Badgers;loss",
        "Blithering Badgers;Devastating Donkeys;loss",
        "Allegoric Alaskans;Courageous Californians;win",
    ]
    assert lines_of(tally(rows)) == lines_of(tally(list(reversed(rows))))


def test_no_matches_gives_only_header():
    assert lines_of(tally([])) == [HEADER]
