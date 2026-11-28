from tournament import tally


def _as_text(result):
    if isinstance(result, bytes):
        result = result.decode("utf-8")
    if isinstance(result, str):
        return result
    return "\n".join(str(line) for line in result)


def _parse_table(result):
    table = []
    for line in _as_text(result).splitlines():
        if "|" not in line:
            continue
        cells = [cell.strip() for cell in line.split("|")]
        if len(cells) != 6 or cells[0] == "Team":
            continue
        team, mp, w, d, l, p = cells
        table.append(
            {
                "team": team,
                "mp": int(mp),
                "w": int(w),
                "d": int(d),
                "l": int(l),
                "p": int(p),
            }
        )
    return table


def _as_tuples(table):
    return [
        (r["team"], r["mp"], r["w"], r["d"], r["l"], r["p"]) for r in table
    ]


def _by_team(result):
    return {r["team"]: r for r in _parse_table(result)}


EXAMPLE_INPUT = [
    "Allegoric Alaskans;Blithering Badgers;win",
    "Devastating Donkeys;Courageous Californians;draw",
    "Devastating Donkeys;Allegoric Alaskans;win",
    "Courageous Californians;Blithering Badgers;loss",
    "Blithering Badgers;Devastating Donkeys;loss",
    "Allegoric Alaskans;Courageous Californians;win",
]

EXAMPLE_TABLE = [
    ("Devastating Donkeys", 3, 2, 1, 0, 7),
    ("Allegoric Alaskans", 3, 2, 0, 1, 6),
    ("Blithering Badgers", 3, 1, 0, 2, 3),
    ("Courageous Californians", 3, 0, 1, 2, 1),
]


def test_example_table_matches_requirements():
    # SRC: "create a file with a table like this:"
    assert _as_tuples(_parse_table(tally(EXAMPLE_INPUT))) == EXAMPLE_TABLE


def test_example_teams_ordered_by_points_descending():
    table = _parse_table(tally(EXAMPLE_INPUT))
    # SRC: "The outcome is ordered by points, descending."
    assert [r["team"] for r in table] == [
        "Devastating Donkeys",
        "Allegoric Alaskans",
        "Blithering Badgers",
        "Courageous Californians",
    ]


def test_win_earns_three_points():
    by_team = _by_team(tally(["Alpha;Beta;win"]))
    # SRC: "A win earns a team 3 points."
    assert by_team["Alpha"]["p"] == 3


def test_loss_earns_zero_points():
    by_team = _by_team(tally(["Alpha;Beta;win"]))
    # SRC: "A loss earns 0."
    assert by_team["Beta"]["p"] == 0


def test_draw_earns_one_point_each():
    by_team = _by_team(tally(["Alpha;Beta;draw"]))
    # SRC: "A draw earns 1."
    assert by_team["Alpha"]["p"] == 1
    # SRC: "A draw earns 1."
    assert by_team["Beta"]["p"] == 1


def test_first_listed_team_is_the_winner_on_win():
    by_team = _by_team(tally(["Allegoric Alaskans;Blithering Badgers;win"]))
    # SRC: "means that the Allegoric Alaskans beat the Blithering Badgers."
    assert by_team["Allegoric Alaskans"]["w"] == 1
    # SRC: "means that the Allegoric Alaskans beat the Blithering Badgers."
    assert by_team["Blithering Badgers"]["l"] == 1


def test_loss_on_first_listed_team_means_second_team_won():
    by_team = _by_team(tally(["Courageous Californians;Blithering Badgers;loss"]))
    # SRC: "means that the Blithering Badgers beat the Courageous Californians."
    assert by_team["Blithering Badgers"]["w"] == 1
    # SRC: "means that the Blithering Badgers beat the Courageous Californians."
    assert by_team["Courageous Californians"]["l"] == 1


def test_draw_example_sentence_ties_both_teams():
    by_team = _by_team(
        tally(["Devastating Donkeys;Courageous Californians;draw"])
    )
    # SRC: "means that the Devastating Donkeys and Courageous Californians tied."
    assert by_team["Devastating Donkeys"]["d"] == 1
    # SRC: "means that the Devastating Donkeys and Courageous Californians tied."
    assert by_team["Courageous Californians"]["d"] == 1


def test_tied_points_ordered_alphabetically():
    table = _parse_table(tally(["Zeta;Alpha;draw"]))
    # SRC: "In case of a tie, teams are ordered alphabetically."
    assert [r["team"] for r in table] == ["Alpha", "Zeta"]


def test_matches_played_counts_all_matches():
    by_team = _by_team(tally(EXAMPLE_INPUT))
    # SRC: "MP: Matches Played"
    assert by_team["Devastating Donkeys"]["mp"] == 3


def test_matches_drawn_counts_ties():
    by_team = _by_team(tally(EXAMPLE_INPUT))
    # SRC: "D: Matches Drawn (Tied)"
    assert by_team["Courageous Californians"]["d"] == 1
