from yacht import (
    YACHT,
    ONES,
    TWOS,
    THREES,
    FOURS,
    FIVES,
    SIXES,
    FULL_HOUSE,
    FOUR_OF_A_KIND,
    LITTLE_STRAIGHT,
    BIG_STRAIGHT,
    CHOICE,
    score,
)


def test_upper_section_examples_from_spec():
    assert score([1, 1, 1, 4, 5], ONES) == 3
    assert score([2, 2, 3, 4, 5], TWOS) == 4
    assert score([3, 3, 3, 3, 3], THREES) == 15
    assert score([1, 2, 3, 3, 5], FOURS) == 0
    assert score([5, 1, 5, 2, 5], FIVES) == 15
    assert score([2, 3, 4, 5, 6], SIXES) == 6


def test_upper_section_with_no_matching_dice_scores_zero():
    assert score([2, 3, 4, 5, 6], ONES) == 0


def test_upper_section_with_all_matching_dice():
    assert score([6, 6, 6, 6, 6], SIXES) == 30
    assert score([1, 1, 1, 1, 1], ONES) == 5


def test_full_house_example_from_spec():
    assert score([3, 3, 3, 5, 5], FULL_HOUSE) == 19


def test_full_house_rejects_yacht():
    assert score([4, 4, 4, 4, 4], FULL_HOUSE) == 0


def test_four_of_a_kind_example_from_spec():
    assert score([4, 4, 4, 4, 6], FOUR_OF_A_KIND) == 16


def test_four_of_a_kind_accepts_yacht():
    assert score([4, 4, 4, 4, 4], FOUR_OF_A_KIND) == 16


def test_four_of_a_kind_rejects_full_house():
    assert score([2, 2, 2, 5, 5], FOUR_OF_A_KIND) == 0


def test_little_straight_example_from_spec():
    assert score([1, 2, 3, 4, 5], LITTLE_STRAIGHT) == 30


def test_little_straight_accepts_unordered_dice():
    assert score([5, 3, 1, 4, 2], LITTLE_STRAIGHT) == 30


def test_little_straight_rejects_missing_value():
    assert score([1, 2, 3, 4, 6], LITTLE_STRAIGHT) == 0


def test_big_straight_example_from_spec():
    assert score([2, 3, 4, 5, 6], BIG_STRAIGHT) == 30


def test_big_straight_accepts_unordered_dice():
    assert score([6, 2, 3, 4, 5], BIG_STRAIGHT) == 30


def test_big_straight_rejects_little_straight():
    assert score([1, 2, 3, 4, 5], BIG_STRAIGHT) == 0


def test_choice_example_from_spec():
    assert score([2, 3, 3, 4, 6], CHOICE) == 18


def test_choice_any_combination():
    assert score([6, 6, 6, 6, 6], CHOICE) == 30
    assert score([1, 1, 1, 1, 1], CHOICE) == 5


def test_yacht_example_from_spec():
    assert score([4, 4, 4, 4, 4], YACHT) == 50


def test_yacht_rejects_four_of_a_kind():
    assert score([4, 4, 4, 4, 6], YACHT) == 0


def test_yacht_with_ones():
    assert score([1, 1, 1, 1, 1], YACHT) == 50
