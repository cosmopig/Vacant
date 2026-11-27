import string

from simple_cipher import Cipher


def test_example_dddddd_key_encodes_iamapandabear():
    # SRC: "For example, the plaintext `"iamapandabear"` would become `"ldpdsdqgdehdu"`."
    assert Cipher(key="dddddd").encode("iamapandabear") == "ldpdsdqgdehdu"


def test_example_dddddd_key_decodes_ldpdsdqgdehdu():
    # SRC: "For example, the plaintext `"iamapandabear"` would become `"ldpdsdqgdehdu"`."
    assert Cipher(key="dddddd").decode("ldpdsdqgdehdu") == "iamapandabear"


def test_example_abcd_key_encodes_hello():
    # SRC: "Applying those shifts to the letters of `"hello"` we get `"hfnoo"`."
    assert Cipher(key="abcd").encode("hello") == "hfnoo"


def test_example_abcd_key_decodes_hfnoo():
    # SRC: "Applying those shifts to the letters of `"hello"` we get `"hfnoo"`."
    assert Cipher(key="abcd").decode("hfnoo") == "hello"


def test_key_abcd_shift_distances_on_plaintext_of_a():
    # SRC: "If the key is `"abcd"` then letters of the plaintext would be shifted by a distance of 0, 1, 2, and 3."
    assert Cipher(key="abcd").encode("aaaa") == "abcd"


def test_key_consisting_only_of_a_leaves_text_unchanged():
    # SRC: "If the key only contains the letter `"a"` (one or more times), the shift distance is zero and the ciphertext is the same as the plaintext."
    assert Cipher(key="aa").encode("hello") == "hello"


def test_single_letter_key_z_rotates_with_wraparound():
    # SRC: "Each letter of the plaintext is _shifted_ or _rotated_ by a distance based on a corresponding letter in the key."
    assert Cipher(key="z").encode("abc") == "zab"


def test_key_wraps_around_when_shorter_than_plaintext():
    # SRC: "If you run out of letters in the key before you run out of letters in the plaintext, start over from the start of the key again."
    assert Cipher(key="abcd").encode("aaaaa") == "abcda"


def test_random_key_yields_at_least_100_lowercase_letters():
    # SRC: "If no key is provided, generate a key which consists of at least 100 random lowercase letters from the Latin alphabet."
    key_stream = Cipher().encode("a" * 100)
    assert len(key_stream) >= 100
    # SRC: "If no key is provided, generate a key which consists of at least 100 random lowercase letters from the Latin alphabet."
    assert all(ch in string.ascii_lowercase for ch in key_stream)


def test_random_key_round_trip_decodes_back_to_plaintext():
    # SRC: "Converting plaintext to ciphertext is called _encoding_ while the reverse is called _decoding_."
    cipher = Cipher()
    # SRC: "Converting plaintext to ciphertext is called _encoding_ while the reverse is called _decoding_."
    assert cipher.decode(cipher.encode("hello")) == "hello"
