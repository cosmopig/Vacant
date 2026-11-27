"""Acceptance tests for the kindergarten garden exercise."""
from collections import Counter

from kindergarten_garden import Garden

DEFAULT_ROSTER = [
    "Alice", "Bob", "Charlie", "David", "Eve", "Fred",
    "Ginny", "Harriet", "Ileana", "Joseph", "Kincaid", "Larry",
]
EXAMPLE_DIAGRAM = "VRCGVVRVCGGCCGVRGCVCGCGV\nVRCCCGCRRGVCGCRVVCVGCGCV"
PLANT_NAMES = {"G": "grass", "C": "clover", "R": "radishes", "V": "violets"}
ALLOWED_PLANTS = {"grass", "clover", "radishes", "violets"}


def _norm(plants):
    return [p.lower() for p in plants]


def test_plants_returns_a_list():
    """REQ: "returns the `list` of plant names belonging to that student." """
    result = Garden(EXAMPLE_DIAGRAM).plants("Alice")
    assert isinstance(result, list)


def test_plants_returns_strings_from_known_plant_names():
    """REQ: "returns the `list` of plant names belonging to that student." """
    result = _norm(Garden(EXAMPLE_DIAGRAM).plants("Alice"))
    assert all(isinstance(p, str) for p in result)
    assert all(p in ALLOWED_PLANTS for p in result)


def test_each_letter_maps_to_its_plant_name():
    """REQ: "Four different types of seeds are planted:" (table G/C/R/V)"""
    garden = Garden("GCRV\nGCRV", students=["Alice", "Bob"])
    assert _norm(garden.plants("Alice")) == ["grass", "clover", "grass", "clover"]
    assert _norm(garden.plants("Bob")) == ["radishes", "violets", "radishes", "violets"]


def test_example_alice_plants():
    """REQ: "Then if asked for Alice's plants, it should provide:" """
    garden = Garden(EXAMPLE_DIAGRAM)
    assert _norm(garden.plants("Alice")) == [
        "violets", "radishes", "violets", "radishes"
    ]


def test_example_bob_plants():
    """REQ: "While asking for Bob's plants would yield:" """
    garden = Garden(EXAMPLE_DIAGRAM)
    assert _norm(garden.plants("Bob")) == ["clover", "grass", "clover", "clover"]


def test_last_student_larry_gets_last_cups():
    """REQ: "Their teacher assigns cups to the children alphabetically by their names, which means that Alice comes first and Larry comes last." """
    garden = Garden(EXAMPLE_DIAGRAM)
    assert _norm(garden.plants("Larry")) == ["grass", "violets", "clover", "violets"]


def test_middle_student_harriet_gets_her_cups():
    """REQ: "Their teacher assigns cups to the children alphabetically by their names, which means that Alice comes first and Larry comes last." """
    garden = Garden(EXAMPLE_DIAGRAM)
    assert _norm(garden.plants("Harriet")) == [
        "violets", "radishes", "radishes", "violets"
    ]


def test_default_roster_contains_the_twelve_named_children():
    """REQ: "There are 12 children in the class:" """
    garden = Garden(EXAMPLE_DIAGRAM)
    for name in DEFAULT_ROSTER:
        assert len(garden.plants(name)) == 4


def test_constructor_without_students_uses_default_roster():
    """REQ: "Make a garden based on the default 12-student roster." """
    garden = Garden("VRCGVVRVCGGCCGVRGCVCGCGV\nVRCCCGCRRGVCGCRVVCVGCGCV")
    assert _norm(garden.plants("Alice")) == [
        "violets", "radishes", "violets", "radishes"
    ]
    assert _norm(garden.plants("Bob")) == ["clover", "grass", "clover", "clover"]


def test_each_child_gets_four_plants():
    """REQ: "Each child gets four cups, two on each row:" """
    garden = Garden(EXAMPLE_DIAGRAM)
    for name in DEFAULT_ROSTER:
        assert len(garden.plants(name)) == 4


def test_all_cups_assigned_exactly_once():
    """REQ: "Each child gets four cups, two on each row:" """
    garden = Garden(EXAMPLE_DIAGRAM)
    collected = []
    for name in DEFAULT_ROSTER:
        collected.extend(_norm(garden.plants(name)))
    expected = [PLANT_NAMES[ch] for ch in EXAMPLE_DIAGRAM if ch != "\n"]
    assert Counter(collected) == Counter(expected)


def test_custom_student_list_overrides_roster():
    """REQ: "This should override the twelve student roster provided in the problem statement." """
    garden = Garden("VRCC\nVCGG", students=["Valorie", "Raven"])
    assert _norm(garden.plants("Valorie")) == [
        "violets", "radishes", "violets", "clover"
    ]
    assert _norm(garden.plants("Raven")) == ["clover", "clover", "grass", "grass"]


def test_plants_are_read_left_to_right_nearest_window_first():
    """REQ: "Your program will be given the plants from left-to-right starting with the row nearest the windows." """
    garden = Garden("GRVC\nCGRV", students=["Alice", "Bob"])
    assert _norm(garden.plants("Alice")) == ["grass", "radishes", "clover", "grass"]
    assert _norm(garden.plants("Bob")) == ["violets", "clover", "radishes", "violets"]


def test_single_student_garden_boundary():
    """REQ: "Each child gets four cups, two on each row:" """
    garden = Garden("GR\nCV", students=["Alice"])
    assert _norm(garden.plants("Alice")) == [
        "grass", "radishes", "clover", "violets"
    ]
