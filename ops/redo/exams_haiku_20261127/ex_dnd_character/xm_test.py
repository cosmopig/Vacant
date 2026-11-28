from dnd_character import Character, modifier

ABILITIES = ("strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma")


def test_modifier_lowest_possible_score():
    assert modifier(3) == -4


def test_modifier_rounds_down_for_negative_results():
    assert modifier(9) == -1
    assert modifier(5) == -3
    assert modifier(4) == -3


def test_modifier_for_average_scores_is_zero():
    assert modifier(10) == 0
    assert modifier(11) == 0


def test_modifier_for_positive_scores():
    assert modifier(12) == 1
    assert modifier(14) == 2
    assert modifier(15) == 2
    assert modifier(18) == 4


def test_hitpoints_example_from_requirements():
    # Constitution 3 -> modifier -4 -> hitpoints 10 + (-4) = 6
    assert 10 + modifier(3) == 6


def test_character_has_all_six_abilities():
    character = Character()
    for name in ABILITIES:
        assert hasattr(character, name)


def test_ability_scores_are_integers_in_valid_range():
    # Each ability is the sum of three 6-sided dice: minimum 3, maximum 18.
    for _ in range(100):
        character = Character()
        for name in ABILITIES:
            value = getattr(character, name)
            assert isinstance(value, int)
            assert 3 <= value <= 18


def test_hitpoints_follow_constitution_modifier():
    for _ in range(100):
        character = Character()
        assert character.hitpoints == 10 + modifier(character.constitution)
