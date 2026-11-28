from atbash_cipher import encode, decode


def test_encode_simple_word():
    # SRC: "Encoding `test` gives `gvhg`"
    assert encode("test") == "gvhg"


def test_encode_keeps_digits_and_groups_with_space():
    # SRC: "Encoding `x123 yes` gives `c123b vh`"
    assert encode("x123 yes") == "c123b vh"


def test_decode_simple_word():
    # SRC: "Decoding `gvhg` gives `test`"
    assert decode("gvhg") == "test"


def test_decode_full_sentence_without_spaces():
    # SRC: "Decoding `gsvjf rxpyi ldmul cqfnk hlevi gsvoz abwlt` gives `thequickbrownfoxjumpsoverthelazydog`"
    assert decode("gsvjf rxpyi ldmul cqfnk hlevi gsvoz abwlt") == "thequickbrownfoxjumpsoverthelazydog"


def test_encode_full_alphabet_is_reversed_and_grouped():
    # SRC: "The first letter is replaced with the last letter, the second with the second-last, and so on."
    assert encode("abcdefghijklmnopqrstuvwxyz") == "zyxwv utsrq ponml kjihg fedcb a"


def test_encode_sentence_groups_in_fives():
    # SRC: "Ciphertext is written out in groups of fixed length, the traditional group size being 5 letters"
    assert encode("thequickbrownfoxjumpsoverthelazydog") == "gsvjf rxpyi ldmul cqfnk hlevi gsvoz abwlt"


def test_encode_exactly_five_letters_has_no_space():
    # SRC: "the traditional group size being 5 letters"
    assert encode("abcde") == "zyxwv"


def test_encode_sixth_letter_starts_new_group():
    # SRC: "the traditional group size being 5 letters"
    assert encode("abcdef") == "zyxwv u"


def test_encode_excludes_punctuation():
    # SRC: "punctuation is excluded"
    assert encode("yes!") == "bvh"


def test_encode_leaves_numbers_unchanged():
    # SRC: "leaving numbers unchanged"
    assert encode("123") == "123"


def test_decode_leaves_numbers_unchanged_and_drops_grouping_spaces():
    # SRC: "leaving numbers unchanged"
    assert decode("c123b vh") == "x123yes"
