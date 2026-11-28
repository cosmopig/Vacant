"""Acceptance tests for the Scrabble score exercise."""
from scrabble_score import score


def test_score_returns_an_int():
    """REQ: "compute a word's Scrabble score by summing the values of its letters."
    Property: the result is a plain integer (not bool, float, or str).
    """
    result = score("cabbage")
    assert isinstance(result, int), f"expected int, got {type(result).__name__}"
    assert not isinstance(result, bool), "expected int, got bool"


def test_empty_word_scores_zero():
    """REQ: "compute a word's Scrabble score by summing the values of its letters."
    Property: a word with no letters sums to 0.
    """
    assert score("") == 0


def test_cabbage_example_is_14():
    """REQ: "For example, the word "cabbage" is worth 14 points:"
    Property: the worked example scores 14.
    """
    assert score("cabbage") == 14


def test_one_point_letters():
    """REQ: "The letters are valued as follows:" (A, E, I, O, U, L, N, R, S, T = 1)
    Property: each letter in the 1-point group scores 1.
    """
    for ch in "AEIOULNRST":
        assert score(ch) == 1, f"letter {ch} should score 1, got {score(ch)}"


def test_two_point_letters():
    """REQ: "The letters are valued as follows:" (D, G = 2)
    Property: each letter in the 2-point group scores 2.
    """
    for ch in "DG":
        assert score(ch) == 2, f"letter {ch} should score 2, got {score(ch)}"


def test_three_point_letters():
    """REQ: "The letters are valued as follows:" (B, C, M, P = 3)
    Property: each letter in the 3-point group scores 3.
    """
    for ch in "BCMP":
        assert score(ch) == 3, f"letter {ch} should score 3, got {score(ch)}"


def test_four_point_letters():
    """REQ: "The letters are valued as follows:" (F, H, V, W, Y = 4)
    Property: each letter in the 4-point group scores 4.
    """
    for ch in "FHVWY":
        assert score(ch) == 4, f"letter {ch} should score 4, got {score(ch)}"


def test_five_point_letter_k():
    """REQ: "The letters are valued as follows:" (K = 5)
    Property: the letter K scores 5.
    """
    assert score("K") == 5


def test_eight_point_letters():
    """REQ: "The letters are valued as follows:" (J, X = 8)
    Property: each letter in the 8-point group scores 8.
    """
    for ch in "JX":
        assert score(ch) == 8, f"letter {ch} should score 8, got {score(ch)}"


def test_ten_point_letters():
    """REQ: "The letters are valued as follows:" (Q, Z = 10)
    Property: each letter in the 10-point group scores 10.
    """
    for ch in "QZ":
        assert score(ch) == 10, f"letter {ch} should score 10, got {score(ch)}"


def test_score_is_additive_over_concatenation():
    """REQ: "compute a word's Scrabble score by summing the values of its letters."
    Property: score of a word equals the sum of the scores of its two halves.
    Values: "cabbage" = 14, "cab" = 7, "bage" = 7.
    """
    assert score("cabbage") == score("cab") + score("bage")
    assert score("cab") == 7
    assert score("bage") == 7


def test_repeated_letters_each_counted():
    """REQ: "3 points for B" / "3 points for B" (each occurrence of a letter is counted)
    Property: repeated letters contribute their value once per occurrence.
    """
    assert score("bb") == 6
    assert score("aaa") == 3


def test_uppercase_scores_same_as_lowercase():
    """REQ: "For example, the word "cabbage" is worth 14 points:"
    Property: letter values apply regardless of case, since the table lists uppercase letters
    and the example word is lowercase.
    """
    assert score("CABBAGE") == 14
    assert score("cabbage") == 14
    assert score("CaBbAgE") == 14


def test_letter_order_does_not_change_score():
    """REQ: "compute a word's Scrabble score by summing the values of its letters."
    Property: rearranging the letters of a word does not change its score (sum is order-free).
    Values: "cab" = 7 and each permutation = 7.
    """
    assert score("cab") == 7
    assert score("bac") == 7
    assert score("bca") == 7


def test_high_value_words_sum_correctly():
    """REQ: "compute a word's Scrabble score by summing the values of its letters."
    Property: words built only from high-value letters sum their values.
    Values: Q=10, Z=10, J=8, X=8.
    """
    assert score("QZ") == 20
    assert score("JX") == 16
