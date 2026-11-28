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


def test_score_returns_int_for_valid_input():
    """REQ: "Given five dice and a category, calculate the score of the dice for that category." """
    result = score([1, 2, 3, 4, 5], CHOICE)
    assert isinstance(result, int)
    assert not isinstance(result, bool)


def test_all_categories_are_distinct():
    """REQ: "Given five dice and a category, calculate the score of the dice for that category." """
    categories = {
        YACHT, ONES, TWOS, THREES, FOURS, FIVES, SIXES,
        FULL_HOUSE, FOUR_OF_A_KIND, LITTLE_STRAIGHT, BIG_STRAIGHT, CHOICE,
    }
    assert len(categories) == 12


def test_ones_example():
    """REQ: "Ones | 1 × number of ones | Any combination | 1 1 1 4 5 scores 3" """
    assert score([1, 1, 1, 4, 5], ONES) == 3


def test_twos_example():
    """REQ: "Twos | 2 × number of twos | Any combination | 2 2 3 4 5 scores 4" """
    assert score([2, 2, 3, 4, 5], TWOS) == 4


def test_threes_example():
    """REQ: "Threes | 3 × number of threes | Any combination | 3 3 3 3 3 scores 15" """
    assert score([3, 3, 3, 3, 3], THREES) == 15


def test_fours_example_with_no_matching_dice_scores_zero():
    """REQ: "Fours | 4 × number of fours | Any combination | 1 2 3 3 5 scores 0" """
    assert score([1, 2, 3, 3, 5], FOURS) == 0


def test_fives_example():
    """REQ: "Fives | 5 × number of fives | Any combination | 5 1 5 2 5 scores 15" """
    assert score([5, 1, 5, 2, 5], FIVES) == 15


def test_sixes_example():
    """REQ: "Sixes | 6 × number of sixes | Any combination | 2 3 4 5 6 scores 6" """
    assert score([2, 3, 4, 5, 6], SIXES) == 6


def test_full_house_example():
    """REQ: "Full House | Total of the dice | Three of one number and two of another | 3 3 3 5 5 scores 19" """
    assert score([3, 3, 3, 5, 5], FULL_HOUSE) == 19


def test_four_of_a_kind_example():
    """REQ: "Four of a Kind | Total of the four dice | At least four dice showing the same face | 4 4 4 4 6 scores 16" """
    assert score([4, 4, 4, 4, 6], FOUR_OF_A_KIND) == 16


def test_little_straight_example():
    """REQ: "Little Straight | 30 points | 1-2-3-4-5 | 1 2 3 4 5 scores 30" """
    assert score([1, 2, 3, 4, 5], LITTLE_STRAIGHT) == 30


def test_big_straight_example():
    """REQ: "Big Straight | 30 points | 2-3-4-5-6 | 2 3 4 5 6 scores 30" """
    assert score([2, 3, 4, 5, 6], BIG_STRAIGHT) == 30


def test_choice_example():
    """REQ: "Choice | Sum of the dice | Any combination | 2 3 3 4 6 scores 18" """
    assert score([2, 3, 3, 4, 6], CHOICE) == 18


def test_yacht_example():
    """REQ: "Yacht | 50 points | All five dice showing the same face | 4 4 4 4 4 scores 50" """
    assert score([4, 4, 4, 4, 4], YACHT) == 50


def test_ones_scores_zero_without_ones():
    """REQ: "If the dice do **not** satisfy the requirements of a category, the score is zero." """
    assert score([2, 3, 4, 5, 6], ONES) == 0


def test_ones_with_all_ones_scores_five():
    """REQ: "Ones | 1 × number of ones | Any combination | 1 1 1 1 1 scores 5" """
    assert score([1, 1, 1, 1, 1], ONES) == 5


def test_sixes_with_all_sixes_scores_thirty():
    """REQ: "Sixes | 6 × number of sixes | Any combination | 6 6 6 6 6 scores 30" """
    assert score([6, 6, 6, 6, 6], SIXES) == 30


def test_choice_accepts_boundary_values_one_and_six():
    """REQ: "Each dice's value will be between one and six inclusively." """
    assert score([1, 1, 1, 1, 1], CHOICE) == 5
    assert score([6, 6, 6, 6, 6], CHOICE) == 30


def test_yacht_scores_zero_when_not_all_same_face():
    """REQ: "Yacht | 50 points | All five dice showing the same face | 4 4 4 4 3 scores 0" """
    assert score([4, 4, 4, 4, 3], YACHT) == 0


def test_four_of_a_kind_entered_in_yacht_scores_zero():
    """REQ: "If, for example, _Four Of A Kind_ is entered in the _Yacht_ category, zero points are scored." """
    assert score([4, 4, 4, 4, 6], YACHT) == 0


def test_yacht_entered_in_full_house_scores_zero():
    """REQ: "A _Yacht_ scores zero if entered in the _Full House_ category." """
    assert score([4, 4, 4, 4, 4], FULL_HOUSE) == 0


def test_full_house_rejects_three_and_three_split():
    """REQ: "Full House | Total of the dice | Three of one number and two of another" """
    assert score([2, 2, 2, 3, 3], FULL_HOUSE) == 0 or score([2, 2, 2, 3, 3], FULL_HOUSE) == 12
    assert score([1, 2, 3, 4, 5], FULL_HOUSE) == 0


def test_full_house_rejects_four_and_one():
    """REQ: "Full House | Total of the dice | Three of one number and two of another" """
    assert score([2, 2, 2, 2, 3], FULL_HOUSE) == 0


def test_four_of_a_kind_scores_zero_without_four_matching():
    """REQ: "Four of a Kind | Total of the four dice | At least four dice showing the same face" """
    assert score([4, 4, 4, 5, 5], FOUR_OF_A_KIND) == 0


def test_little_straight_scores_zero_for_non_straight():
    """REQ: "Little Straight | 30 points | 1-2-3-4-5" """
    assert score([1, 2, 3, 4, 6], LITTLE_STRAIGHT) == 0


def test_big_straight_scores_zero_for_non_straight():
    """REQ: "Big Straight | 30 points | 2-3-4-5-6" """
    assert score([1, 2, 3, 4, 5], BIG_STRAIGHT) == 0


def test_scores_do_not_depend_on_dice_order():
    """REQ: "The dice may be unordered." """
    assert score([5, 3, 5, 3, 3], FULL_HOUSE) == 19
    assert score([5, 4, 3, 2, 1], LITTLE_STRAIGHT) == 30
    assert score([6, 2, 5, 3, 4], BIG_STRAIGHT) == 30
    assert score([5, 1, 5, 2, 5], FIVES) == 15


def test_scoring_is_deterministic_across_repeated_calls():
    """REQ: "Given five dice and a category, calculate the score of the dice for that category." """
    first = score([2, 3, 3, 4, 6], CHOICE)
    second = score([2, 3, 3, 4, 6], CHOICE)
    assert first == second == 18
