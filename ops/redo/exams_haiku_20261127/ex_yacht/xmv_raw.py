from yacht import (
    score,
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
)


def test_number_categories_score_face_value_times_count():
    # SRC: "1 1 1 4 5 scores 3"
    assert score([1, 1, 1, 4, 5], ONES) == 3
    # SRC: "2 2 3 4 5 scores 4"
    assert score([2, 2, 3, 4, 5], TWOS) == 4
    # SRC: "3 3 3 3 3 scores 15"
    assert score([3, 3, 3, 3, 3], THREES) == 15
    # SRC: "5 1 5 2 5 scores 15"
    assert score([5, 1, 5, 2, 5], FIVES) == 15
    # SRC: "2 3 4 5 6 scores 6"
    assert score([2, 3, 4, 5, 6], SIXES) == 6


def test_number_category_with_no_matching_dice_scores_zero():
    # SRC: "1 2 3 3 5 scores 0"
    assert score([1, 2, 3, 3, 5], FOURS) == 0


def test_full_house_scores_total_of_dice():
    # SRC: "3 3 3 5 5 scores 19"
    assert score([3, 3, 3, 5, 5], FULL_HOUSE) == 19
    # SRC: "The dice may be unordered."
    assert score([5, 3, 5, 3, 3], FULL_HOUSE) == 19
    # SRC: "Three of one number and two of another"
    assert score([3, 3, 3, 3, 3], FULL_HOUSE) == 0


def test_four_of_a_kind_scores_total_of_four_dice():
    # SRC: "4 4 4 4 6 scores 16"
    assert score([4, 4, 4, 4, 6], FOUR_OF_A_KIND) == 16


def test_straights_score_30():
    # SRC: "1 2 3 4 5 scores 30"
    assert score([1, 2, 3, 4, 5], LITTLE_STRAIGHT) == 30
    # SRC: "The dice may be unordered."
    assert score([5, 3, 1, 4, 2], LITTLE_STRAIGHT) == 30
    # SRC: "2 3 4 5 6 scores 30"
    assert score([2, 3, 4, 5, 6], BIG_STRAIGHT) == 30


def test_choice_scores_sum_of_dice():
    # SRC: "2 3 3 4 6 scores 18"
    assert score([2, 3, 3, 4, 6], CHOICE) == 18


def test_yacht_scores_50_when_all_dice_match():
    # SRC: "4 4 4 4 4 scores 50"
    assert score([4, 4, 4, 4, 4], YACHT) == 50
    # SRC: "All five dice showing the same face"
    assert score([6, 6, 6, 6, 6], YACHT) == 50


def test_dice_not_satisfying_category_score_zero():
    # SRC: "If the dice do **not** satisfy the requirements of a category, the score is zero."
    assert score([4, 4, 4, 4, 6], YACHT) == 0
    # SRC: "If the dice do **not** satisfy the requirements of a category, the score is zero."
    assert score([2, 3, 4, 5, 6], LITTLE_STRAIGHT) == 0
    # SRC: "A _Yacht_ scores zero if entered in the _Full House_ category."
    assert score([4, 4, 4, 4, 4], FULL_HOUSE) == 0
