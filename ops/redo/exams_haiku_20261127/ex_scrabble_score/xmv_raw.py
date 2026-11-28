from scrabble_score import score


def test_example_word_cabbage_is_worth_14():
    # SRC: "is worth 14 points:"
    assert score("cabbage") == 14


def test_single_one_point_letter():
    # SRC: "1 point for A"
    assert score("a") == 1


def test_two_point_letters_dog():
    # SRC: "D, G"
    assert score("dog") == 5


def test_three_point_letters_bob():
    # SRC: "B, C, M, P"
    assert score("bob") == 7


def test_four_point_letter():
    # SRC: "F, H, V, W, Y"
    assert score("f") == 4


def test_four_point_letters_fly():
    # SRC: "F, H, V, W, Y"
    assert score("fly") == 9


def test_five_point_letter_k():
    # SRC: "| K                            | 5     |"
    assert score("k") == 5


def test_eight_point_letters_jx():
    # SRC: "J, X"
    assert score("jx") == 16


def test_ten_point_letters_qz():
    # SRC: "Q, Z"
    assert score("qz") == 20


def test_all_one_point_letters_sum_to_ten():
    # SRC: "A, E, I, O, U, L, N, R, S, T"
    assert score("aeioulnrst") == 10
