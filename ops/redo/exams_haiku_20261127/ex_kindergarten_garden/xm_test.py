import pytest

from kindergarten_garden import Garden


DEFAULT_DIAGRAM = (
    "VRCGVVRVCGGCCGVRGCVCGCGV\n"
    "VRCCCGCRRGVCGCRVVCVGCGCV"
)


def test_alice_gets_first_two_cups_of_each_row():
    garden = Garden(DEFAULT_DIAGRAM)
    assert garden.plants("Alice") == [
        "violets", "radishes", "violets", "radishes"
    ]


def test_bob_gets_second_pair_of_cups():
    garden = Garden(DEFAULT_DIAGRAM)
    assert garden.plants("Bob") == [
        "clover", "grass", "clover", "clover"
    ]


def test_charlie_result_is_a_list_of_four_plants():
    result = Garden(DEFAULT_DIAGRAM).plants("Charlie")
    assert isinstance(result, list)
    assert len(result) == 4
    assert result == ["violets", "violets", "clover", "grass"]


def test_ginny_plants_from_middle_of_roster():
    garden = Garden(DEFAULT_DIAGRAM)
    assert garden.plants("Ginny") == [
        "clover", "grass", "grass", "clover"
    ]


def test_harriet_plants_with_radishes_in_second_row():
    garden = Garden(DEFAULT_DIAGRAM)
    assert garden.plants("Harriet") == [
        "violets", "radishes", "radishes", "violets"
    ]


def test_kincaid_plants():
    garden = Garden(DEFAULT_DIAGRAM)
    assert garden.plants("Kincaid") == [
        "grass", "clover", "clover", "grass"
    ]


def test_larry_is_last_child_on_default_roster():
    garden = Garden(DEFAULT_DIAGRAM)
    assert garden.plants("Larry") == [
        "grass", "violets", "clover", "violets"
    ]


def test_each_student_gets_four_cups_on_default_roster():
    garden = Garden(DEFAULT_DIAGRAM)
    roster = [
        "Alice", "Bob", "Charlie", "David", "Eve", "Fred",
        "Ginny", "Harriet", "Ileana", "Joseph", "Kincaid", "Larry",
    ]
    for name in roster:
        assert len(garden.plants(name)) == 4


def test_custom_roster_overrides_default_first_student():
    garden = Garden("VRCC\nVCGG", students=["Valorie", "Raven"])
    assert garden.plants("Valorie") == [
        "violets", "radishes", "violets", "clover"
    ]


def test_custom_roster_second_student():
    garden = Garden("VRCC\nVCGG", students=["Valorie", "Raven"])
    assert garden.plants("Raven") == [
        "clover", "clover", "grass", "grass"
    ]


def test_single_student_roster_with_one_cup_pair_per_row():
    garden = Garden("RG\nCV", students=["Alice"])
    assert garden.plants("Alice") == [
        "radishes", "grass", "clover", "violets"
    ]
