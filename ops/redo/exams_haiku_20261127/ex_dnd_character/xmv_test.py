from dnd_character import Character, modifier

ABILITIES = ("strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma")


def test_modifier_of_constitution_three_is_minus_four():
    # SRC: "Because constitution is 3, the constitution modifier is -4 and the hitpoints are 6."
    assert modifier(3) == -4


def test_modifier_of_ten_is_zero():
    # SRC: "You find your character's constitution modifier by subtracting 10 from your character's constitution, divide by 2 and round down."
    assert modifier(10) == 0


def test_modifier_rounds_down_for_nine():
    # SRC: "You find your character's constitution modifier by subtracting 10 from your character's constitution, divide by 2 and round down."
    assert modifier(9) == -1


def test_modifier_rounds_down_for_eleven():
    # SRC: "You find your character's constitution modifier by subtracting 10 from your character's constitution, divide by 2 and round down."
    assert modifier(11) == 0


def test_modifier_for_even_score_below_ten():
    # SRC: "You find your character's constitution modifier by subtracting 10 from your character's constitution, divide by 2 and round down."
    assert modifier(4) == -3


def test_modifier_for_odd_score_above_ten():
    # SRC: "You find your character's constitution modifier by subtracting 10 from your character's constitution, divide by 2 and round down."
    assert modifier(15) == 2


def test_modifier_of_eighteen_is_four():
    # SRC: "You find your character's constitution modifier by subtracting 10 from your character's constitution, divide by 2 and round down."
    assert modifier(18) == 4


def test_hitpoints_equal_ten_plus_constitution_modifier():
    for _ in range(20):
        character = Character()
        # SRC: "Your character's initial hitpoints are 10 + your character's constitution modifier."
        assert character.hitpoints == 10 + modifier(character.constitution)


def test_hitpoints_within_bounds_implied_by_score_range():
    for _ in range(20):
        character = Character()
        # SRC: "Your character's initial hitpoints are 10 + your character's constitution modifier."
        assert 6 <= character.hitpoints <= 14


def test_each_ability_score_is_sum_of_three_of_four_six_sided_dice():
    for _ in range(20):
        character = Character()
        for name in ABILITIES:
            value = getattr(character, name)
            # SRC: "You do this by rolling four 6-sided dice and recording the sum of the largest three dice."
            assert 3 <= value <= 18
