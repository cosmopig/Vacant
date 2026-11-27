from atbash_cipher import encode, decode


def test_encode_simple_word():
    assert encode("test") == "gvhg"


def test_encode_keeps_digits_and_drops_punctuation_and_spaces():
    # Digits are unchanged, the space is removed, and letters inside a group are counted.
    assert encode("x123 yes") == "c123b vh"


def test_encode_drops_punctuation():
    assert encode("Stop!") == "hglk"


def test_encode_is_case_insensitive_and_outputs_lowercase():
    assert encode("TEST") == "gvhg"


def test_encode_exactly_five_letters_has_no_trailing_space():
    assert encode("abcde") == "zyxwv"


def test_encode_groups_of_five_letters():
    assert encode("abcdef") == "zyxwv u"


def test_encode_middle_letters_swap_with_neighbours():
    assert encode("mn") == "nm"


def test_encode_digits_count_toward_group_length():
    assert encode("123456") == "12345 6"


def test_encode_full_sentence_matches_known_ciphertext():
    assert encode("The quick brown fox jumps over the lazy dog.") == (
        "gsvjf rxpyi ldmul cqfnk hlevi gsvoz abwlt"
    )


def test_encode_empty_string():
    assert encode("") == ""


def test_decode_simple_word():
    assert decode("gvhg") == "test"


def test_decode_removes_group_spaces_and_keeps_digits():
    assert decode("c123b vh") == "x123yes"


def test_decode_full_sentence_has_no_spaces_in_output():
    assert decode("gsvjf rxpyi ldmul cqfnk hlevi gsvoz abwlt") == (
        "thequickbrownfoxjumpsoverthelazydog"
    )


def test_decode_empty_string():
    assert decode("") == ""


def test_round_trip_letters_only():
    text = "thequickbrownfoxjumpsoverthelazydog"
    assert decode(encode(text)) == text


def test_round_trip_with_digits():
    text = "123abc456"
    assert decode(encode(text)) == text
