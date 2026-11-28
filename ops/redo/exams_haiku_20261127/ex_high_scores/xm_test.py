# Acceptance tests for the High Scores exercise.
# Method names follow the usual Exercism High Scores API: latest(),
# personal_best(), and personal_top_three(). The stub does not name them,
# so adjust these calls if the solution uses different names.
from high_scores import HighScores


def test_latest_returns_last_added_score():
    assert HighScores([100, 0, 90, 30]).latest() == 30


def test_latest_with_single_zero_score():
    assert HighScores([0]).latest() == 0


def test_personal_best_is_highest_score():
    assert HighScores([40, 100, 70]).personal_best() == 100


def test_personal_best_when_highest_is_first_and_last_is_lower():
    assert HighScores([100, 0, 90, 30]).personal_best() == 100


def test_personal_best_with_single_score():
    assert HighScores([5]).personal_best() == 5


def test_personal_best_with_repeated_maximum():
    assert HighScores([5, 5]).personal_best() == 5


def test_top_three_in_descending_order_from_three_scores():
    assert HighScores([20, 10, 30]).personal_top_three() == [30, 20, 10]


def test_top_three_from_longer_list():
    scores = [10, 30, 90, 30, 100, 20, 10, 0, 30, 40, 40, 70, 70]
    assert HighScores(scores).personal_top_three() == [100, 90, 70]


def test_top_three_with_fewer_than_three_scores_returns_all_descending():
    assert HighScores([70, 50]).personal_top_three() == [70, 50]


def test_top_three_with_single_score():
    assert HighScores([20]).personal_top_three() == [20]


def test_top_three_keeps_duplicate_values_as_separate_scores():
    assert HighScores([30, 30, 30, 20]).personal_top_three() == [30, 30, 30]
