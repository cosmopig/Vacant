# Acceptance tests for the kindergarten garden exercise.
# Plant names are compared case-insensitively because the requirements capitalise them inconsistently.
# Default roster order (alphabetical): Alice, Bob, Charlie, David, Eve, Fred, Ginny, Harriet, Ileana, Joseph, Kincaid, Larry.
# Child k (0-indexed) owns columns 2k and 2k+1 in each of the two rows.

from kindergarten_garden import Garden


EXAMPLE_DIAGRAM = "VRCGVVRVCGGCCGVRGCVCGCGV\nVRCCCGCRRGVCGCRVVCVGCGCV"


def _norm(plants):
    return [str(p).lower() for p in plants]


def test_alice_plants_from_requirements_example():
    garden = Garden(EXAMPLE_DIAGRAM)
    # SRC: "Violets, radishes, violets, radishes"
    assert _norm(garden.plants("Alice")) == ["violets", "radishes", "violets", "radishes"]


def test_bob_plants_from_requirements_example():
    garden = Garden(EXAMPLE_DIAGRAM)
    # SRC: "Clover, grass, clover, clover"
    assert _norm(garden.plants("Bob")) == ["clover", "grass", "clover", "clover"]


def test_plants_listed_row_nearest_windows_first_then_left_to_right():
    garden = Garden("VR\nGC", students=["Alice"])
    # SRC: "Your program will be given the plants from left-to-right starting with the row nearest the windows."
    assert _norm(garden.plants("Alice")) == ["violets", "radishes", "grass", "clover"]


def test_charlie_middle_child_in_default_roster():
    garden = Garden(EXAMPLE_DIAGRAM)
    # SRC: "Each child gets four cups, two on each row:"
    assert _norm(garden.plants("Charlie")) == ["violets", "violets", "clover", "grass"]


def test_fred_child_in_default_roster():
    garden = Garden(EXAMPLE_DIAGRAM)
    # SRC: "Each child gets four cups, two on each row:"
    assert _norm(garden.plants("Fred")) == ["grass", "clover", "violets", "clover"]


def test_ginny_child_in_default_roster():
    garden = Garden(EXAMPLE_DIAGRAM)
    # SRC: "Each child gets four cups, two on each row:"
    assert _norm(garden.plants("Ginny")) == ["clover", "grass", "grass", "clover"]


def test_joseph_child_in_default_roster():
    garden = Garden(EXAMPLE_DIAGRAM)
    # SRC: "Each child gets four cups, two on each row:"
    assert _norm(garden.plants("Joseph")) == ["violets", "clover", "violets", "grass"]


def test_kincaid_child_in_default_roster():
    garden = Garden(EXAMPLE_DIAGRAM)
    # SRC: "Each child gets four cups, two on each row:"
    assert _norm(garden.plants("Kincaid")) == ["grass", "clover", "clover", "grass"]


def test_larry_is_last_child_in_default_roster():
    garden = Garden(EXAMPLE_DIAGRAM)
    # SRC: "Their teacher assigns cups to the children alphabetically by their names, which means that Alice comes first and Larry comes last."
    assert _norm(garden.plants("Larry")) == ["grass", "violets", "clover", "violets"]


def test_custom_students_override_default_roster():
    garden = Garden("VRCC\nVCGG", students=["Valorie", "Raven"])
    # SRC: "This should override the twelve student roster provided in the problem statement."
    assert _norm(garden.plants("Valorie")) == ["violets", "radishes", "violets", "clover"]


def test_custom_students_second_child():
    garden = Garden("VRCC\nVCGG", students=["Valorie", "Raven"])
    # SRC: "This should override the twelve student roster provided in the problem statement."
    assert _norm(garden.plants("Raven")) == ["clover", "clover", "grass", "grass"]


def test_each_seed_letter_maps_to_its_plant_name():
    garden = Garden("GCRV\nGCRV", students=["Alice", "Bob"])
    # SRC: "Four different types of seeds are planted:"
    assert _norm(garden.plants("Alice")) == ["grass", "clover", "grass", "clover"]


def test_each_seed_letter_maps_to_its_plant_name_second_child():
    garden = Garden("GCRV\nGCRV", students=["Alice", "Bob"])
    # SRC: "Four different types of seeds are planted:"
    assert _norm(garden.plants("Bob")) == ["radishes", "violets", "radishes", "violets"]


def test_plants_returns_a_list():
    garden = Garden(EXAMPLE_DIAGRAM)
    # SRC: "returns the `list` of plant names belonging to that student."
    assert isinstance(garden.plants("Alice"), list)
