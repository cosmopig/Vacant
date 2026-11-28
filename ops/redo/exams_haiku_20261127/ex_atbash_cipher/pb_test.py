"""Acceptance tests for the Atbash cipher module (encode and decode)."""
from atbash_cipher import encode, decode


def test_encode_returns_str():
    """REQ: "Encoding `test` gives `gvhg`" - encode returns a string."""
    assert isinstance(encode("test"), str)


def test_decode_returns_str():
    """REQ: "Decoding `gvhg` gives `test`" - decode returns a string."""
    assert isinstance(decode("gvhg"), str)


def test_encode_example_test():
    """REQ: "Encoding `test` gives `gvhg`" - the word test encodes to gvhg."""
    assert encode("test") == "gvhg"


def test_encode_example_numbers_and_space():
    """REQ: "Encoding `x123 yes` gives `c123b vh`" - digits stay, input space is replaced by group spacing."""
    assert encode("x123 yes") == "c123b vh"


def test_decode_example_test():
    """REQ: "Decoding `gvhg` gives `test`" - gvhg decodes to test."""
    assert decode("gvhg") == "test"


def test_decode_example_pangram():
    """REQ: "Decoding `gsvjf rxpyi ldmul cqfnk hlevi gsvoz abwlt` gives `thequickbrownfoxjumpsoverthelazydog`" - grouped ciphertext decodes to the pangram."""
    assert decode("gsvjf rxpyi ldmul cqfnk hlevi gsvoz abwlt") == "thequickbrownfoxjumpsoverthelazydog"


def test_encode_full_alphabet_mapping():
    """REQ: "The first letter is replaced with the last letter, the second with the second-last, and so on." - the alphabet is reversed (a->z ... z->a), grouped in fives."""
    assert encode("abcdefghijklmnopqrstuvwxyz") == "zyxwv utsrq ponml kjihg fedcb a"


def test_encode_pangram_grouped_in_fives():
    """REQ: "Ciphertext is written out in groups of fixed length, the traditional group size being 5 letters" - the pangram is encoded in groups of 5."""
    assert encode("thequickbrownfoxjumpsoverthelazydog") == "gsvjf rxpyi ldmul cqfnk hlevi gsvoz abwlt"


def test_group_size_exactly_five_has_no_trailing_space():
    """REQ: "Ciphertext is written out in groups of fixed length, the traditional group size being 5 letters" - exactly 5 letters form one group with no trailing space."""
    assert encode("abcde") == "zyxwv"


def test_group_size_six_letters_gives_two_groups():
    """REQ: "Ciphertext is written out in groups of fixed length, the traditional group size being 5 letters" - the 6th letter starts a second group."""
    assert encode("abcdef") == "zyxwv u"


def test_encode_leaves_digits_unchanged():
    """REQ: "leaving numbers unchanged" - encoding digit-only text returns the same digits, grouped in fives."""
    assert encode("1234") == "1234"
    assert encode("90210") == "90210"


def test_decode_leaves_digits_unchanged():
    """REQ: "leaving numbers unchanged" - decoding c123b vh gives x123yes, with digits untouched."""
    assert decode("c123b vh") == "x123yes"


def test_encode_excludes_punctuation():
    """REQ: "punctuation is excluded." - punctuation marks are dropped before encoding."""
    assert encode("x123! yes?") == "c123b vh"


def test_decode_ignores_spaces_in_ciphertext():
    """REQ: "Ciphertext is written out in groups of fixed length" - group spaces in ciphertext do not change the decoded text."""
    assert decode("gsvjf rxpyi") == "thequickbrown"
    assert decode("gsvjfrxpyi") == "thequickbrown"


def test_encode_output_is_lowercase():
    """REQ: "All text will be encoded as lowercase letters." - encoded output letters are lowercase."""
    out = encode("thequickbrownfoxjumpsoverthelazydog")
    assert out == out.lower()


def test_decode_output_is_lowercase():
    """REQ: "All text will be encoded as lowercase letters." - decoded output letters are lowercase."""
    out = decode("gsvjf rxpyi ldmul cqfnk hlevi gsvoz abwlt")
    assert out == out.lower()


def test_decode_inverts_encode():
    """REQ: "Decoding `gvhg` gives `test`" - decoding an encoded text returns the original (lowercase, letters and digits only)."""
    assert decode(encode("thequickbrownfoxjumpsoverthelazydog")) == "thequickbrownfoxjumpsoverthelazydog"
    assert decode(encode("x123yes")) == "x123yes"


def test_encode_inverts_decode():
    """REQ: "Decoding `gsvjf rxpyi ldmul cqfnk hlevi gsvoz abwlt` gives `thequickbrownfoxjumpsoverthelazydog`" - encoding the decoded text reproduces the grouped ciphertext."""
    cipher = "gsvjf rxpyi ldmul cqfnk hlevi gsvoz abwlt"
    assert encode(decode(cipher)) == cipher


def test_space_in_input_only_affects_grouping():
    """REQ: "Encoding `x123 yes` gives `c123b vh`" - input spaces are not encoded; output spacing comes only from grouping."""
    assert encode("x123 yes") == encode("x123yes")
