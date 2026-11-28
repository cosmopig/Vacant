"""Acceptance tests for the high-score exercise.

The requirements text describes three operations (highest score, last added
score, three highest scores) but does not name the methods. These tests use
the conventional names for this exercise: latest(), personal_best() and
personal_top_three(). Change the names here if the solution uses others.
"""
from high_scores import HighScores


def test_latest_returns_last_added_score():
    # SRC: "the last added score"
    assert HighScores([100, 0, 90, 30]).latest() == 30
    # SRC: "the last added score"
    assert HighScores([42]).latest() == 42
    # SRC: "the last added score"
    assert HighScores([5, 300, 7]).latest() == 7


def test_personal_best_returns_highest_score():
    # SRC: "return the highest score from the list"
    assert HighScores([100, 0, 90, 30]).personal_best() == 100
    # SRC: "return the highest score from the list"
    assert HighScores([5, 300, 7]).personal_best() == 300
    # SRC: "return the highest score from the list"
    assert HighScores([42]).personal_best() == 42


def test_personal_top_three_returns_three_highest_in_descending_order():
    # SRC: "the three highest scores"
    assert HighScores([100, 0, 90, 30]).personal_top_three() == [100, 90, 30]
    # SRC: "the three highest scores"
    assert HighScores([10, 30, 20]).personal_top_three() == [30, 20, 10]
    # SRC: "the three highest scores"
    assert HighScores([20, 80, 50, 10, 70]).personal_top_three() == [80, 70, 50]


def test_personal_top_three_with_fewer_than_three_scores():
    # SRC: "the three highest scores"
    assert HighScores([40, 10]).personal_top_three() == [40, 10]
    # SRC: "the three highest scores"
    assert HighScores([42]).personal_top_three() == [42]
