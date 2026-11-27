"""Acceptance checks for the High Score list exercise.

The stub only defines HighScores(scores). The requirements describe three
behaviours (highest score, last added score, three highest scores) but do not
name their methods, so this file uses the exercise's conventional names:
personal_best(), latest() and personal_top_three().
The requirements give no numeric sample data, so all sample data below is
chosen by hand and every expected value is worked out from it.
"""

from high_scores import HighScores


def test_constructor_accepts_list_and_creates_high_score_list():
    """REQ: "Manage a game player's High Score list." """
    hs = HighScores([10, 20, 30])
    assert isinstance(hs, HighScores)


def test_personal_best_returns_highest_score_of_example_list():
    """REQ: "write methods that return the highest score from the list" """
    scores = [10, 30, 90, 30, 100, 20, 10, 0, 30, 40, 40, 70, 70]
    assert HighScores(scores).personal_best() == 100


def test_personal_best_finds_maximum_regardless_of_position():
    """REQ: "write methods that return the highest score from the list" """
    scores = [5, 1000, 7]
    assert HighScores(scores).personal_best() == 1000


def test_personal_best_with_single_score_returns_that_score():
    """REQ: "write methods that return the highest score from the list" """
    scores = [42]
    assert HighScores(scores).personal_best() == 42


def test_personal_best_returns_integer_for_integer_scores():
    """REQ: "write methods that return the highest score from the list" """
    scores = [10, 30, 100]
    result = HighScores(scores).personal_best()
    assert isinstance(result, int)
    assert result == 100


def test_latest_returns_last_added_score_of_example_list():
    """REQ: "write methods that return the highest score from the list, the last added score and the three highest scores." """
    scores = [10, 30, 90, 30, 100, 20, 10, 0, 30, 40, 40, 70, 70]
    assert HighScores(scores).latest() == 70


def test_latest_is_last_added_score_not_highest_score():
    """REQ: "write methods that return the highest score from the list, the last added score and the three highest scores." """
    scores = [100, 0]
    assert HighScores(scores).latest() == 0


def test_latest_with_single_score_returns_that_score():
    """REQ: "write methods that return the highest score from the list, the last added score and the three highest scores." """
    scores = [42]
    assert HighScores(scores).latest() == 42


def test_latest_returns_integer_for_integer_scores():
    """REQ: "write methods that return the highest score from the list, the last added score and the three highest scores." """
    scores = [10, 30, 70]
    result = HighScores(scores).latest()
    assert isinstance(result, int)
    assert result == 70


def test_personal_top_three_returns_three_highest_of_example_list():
    """REQ: "write methods that return the highest score from the list, the last added score and the three highest scores." """
    scores = [10, 30, 90, 30, 100, 20, 10, 0, 30, 40, 40, 70, 70]
    result = HighScores(scores).personal_top_three()
    assert sorted(result) == [70, 90, 100]


def test_personal_top_three_has_three_entries_when_enough_scores():
    """REQ: "write methods that return the highest score from the list, the last added score and the three highest scores." """
    scores = [10, 20, 30, 40]
    result = HighScores(scores).personal_top_three()
    assert len(result) == 3


def test_personal_top_three_keeps_repeated_top_values():
    """REQ: "write methods that return the highest score from the list, the last added score and the three highest scores." """
    scores = [30, 30, 30, 10]
    result = HighScores(scores).personal_top_three()
    assert sorted(result) == [30, 30, 30]


def test_personal_top_three_entries_come_from_input_scores():
    """REQ: "write methods that return the highest score from the list, the last added score and the three highest scores." """
    scores = [3, 8, 1, 8, 6]
    result = HighScores(scores).personal_top_three()
    for value in result:
        assert value in scores
    assert sorted(result) == [6, 8, 8]
