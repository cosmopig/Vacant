from scrabble_score import score


def test_example_word_cabbage_is_worth_14():
    assert score("cabbage") == 14


def test_empty_word_scores_zero():
    assert score("") == 0


def test_uppercase_letters_score_the_same_as_lowercase():
    assert score("CABBAGE") == 14


def test_one_point_letters_each_score_one():
    for letter in "aeioulnrst":
        assert score(letter) == 1, letter


def test_all_one_point_letters_together_score_ten():
    assert score("aeioulnrst") == 10


def test_two_point_letters():
    assert score("d") == 2
    assert score("g") == 2


def test_three_point_letters():
    assert score("b") == 3
    assert score("c") == 3
    assert score("m") == 3
    assert score("p") == 3


def test_four_point_letters():
    assert score("f") == 4
    assert score("h") == 4
    assert score("v") == 4
    assert score("w") == 4
    assert score("y") == 4


def test_five_point_letter():
    assert score("k") == 5


def test_eight_point_letters():
    assert score("j") == 8
    assert score("x") == 8


def test_ten_point_letters():
    assert score("q") == 10
    assert score("z") == 10


def test_repeated_letters_are_each_counted():
    assert score("aaa") == 3
    assert score("street") == 6


def test_mixed_tier_words():
    assert score("quiz") == 22
    assert score("jazz") == 29
