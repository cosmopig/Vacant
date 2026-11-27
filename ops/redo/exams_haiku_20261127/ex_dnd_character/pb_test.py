"""Acceptance tests for the D&D character generator (dnd_character).

Each check function is one property taken from the requirements text.
Every check creates its own Character instances and shares no state.
The dice example from the requirements (6, 6, 6, 6 -> 18 etc.) is not
checked directly, because the stub gives no way to control the rolls.
Its consequences are covered by the range and formula properties below.
"""

from dnd_character import Character, modifier

ABILITY_NAMES = (
    "strength",
    "dexterity",
    "constitution",
    "intelligence",
    "wisdom",
    "charisma",
)


def _is_plain_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def test_character_is_class_instantiable_without_arguments():
    """REQ: "For a game of [Dungeons & Dragons][dnd], each player starts by generating a character they can play with." """
    character = Character()
    assert isinstance(Character, type)
    assert character is not None


def test_character_has_six_named_abilities():
    """REQ: "This character has, among other things, six abilities; strength, dexterity, constitution, intelligence, wisdom and charisma." """
    character = Character()
    for name in ABILITY_NAMES:
        assert hasattr(character, name), f"missing ability attribute: {name}"


def test_abilities_are_integers():
    """REQ: "These six abilities have scores that are determined randomly." """
    character = Character()
    for name in ABILITY_NAMES:
        value = getattr(character, name)
        assert _is_plain_int(value), f"{name} is {value!r}, expected an int"


def test_abilities_within_3_to_18():
    """REQ: "You do this by rolling four 6-sided dice and recording the sum of the largest three dice." """
    for _ in range(200):
        character = Character()
        for name in ABILITY_NAMES:
            value = getattr(character, name)
            assert 3 <= value <= 18, f"{name}={value} is outside 3..18"


def test_abilities_vary_between_characters():
    """REQ: "These six abilities have scores that are determined randomly." """
    strengths = {Character().strength for _ in range(100)}
    assert len(strengths) > 1, "strength was identical across 100 characters"


def test_hitpoints_attribute_is_integer():
    """REQ: "Your character's initial hitpoints are 10 + your character's constitution modifier." """
    character = Character()
    assert hasattr(character, "hitpoints")
    assert _is_plain_int(character.hitpoints)


def test_hitpoints_equal_10_plus_constitution_modifier():
    """REQ: "Your character's initial hitpoints are 10 + your character's constitution modifier." """
    for _ in range(100):
        character = Character()
        assert character.hitpoints == 10 + modifier(character.constitution)


def test_hitpoints_within_bounds_implied_by_ability_range():
    """REQ: "Your character's initial hitpoints are 10 + your character's constitution modifier." """
    for _ in range(200):
        character = Character()
        assert 6 <= character.hitpoints <= 14


def test_modifier_returns_integer():
    """REQ: "You find your character's constitution modifier by subtracting 10 from your character's constitution, divide by 2 and round down." """
    for value in (3, 9, 10, 11, 18):
        assert _is_plain_int(modifier(value)), f"modifier({value}) is not an int"


def test_modifier_example_constitution_three_is_minus_four():
    """REQ: "Because constitution is 3, the constitution modifier is -4 and the hitpoints are 6." """
    assert modifier(3) == -4


def test_modifier_is_zero_for_ten_and_eleven():
    """REQ: "You find your character's constitution modifier by subtracting 10 from your character's constitution, divide by 2 and round down." """
    assert modifier(10) == 0
    assert modifier(11) == 0


def test_modifier_positive_for_twelve_and_eighteen():
    """REQ: "You find your character's constitution modifier by subtracting 10 from your character's constitution, divide by 2 and round down." """
    assert modifier(12) == 1
    assert modifier(18) == 4


def test_modifier_rounds_down_for_odd_differences():
    """REQ: "You find your character's constitution modifier by subtracting 10 from your character's constitution, divide by 2 and round down." """
    # Rounding down means -0.5 becomes -1, not 0.
    assert modifier(9) == -1
    assert modifier(7) == -2
    # Rounding down means -4.5 becomes -5.
    assert modifier(1) == -5


def test_modifier_is_non_decreasing_over_ability_range():
    """REQ: "You find your character's constitution modifier by subtracting 10 from your character's constitution, divide by 2 and round down." """
    values = [modifier(score) for score in range(3, 19)]
    assert all(a <= b for a, b in zip(values, values[1:]))
