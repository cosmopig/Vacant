from simple_cipher import Cipher


def test_encode_single_letter_key_shifts_every_letter():
    assert Cipher("dddddd").encode("iamapandabear") == "ldpdsdqgdehdu"


def test_encode_key_wraps_around_when_shorter_than_plaintext():
    assert Cipher("abcd").encode("hello") == "hfnoo"


def test_encode_key_of_only_a_leaves_text_unchanged():
    assert Cipher("aaaaa").encode("hello") == "hello"


def test_encode_shift_of_25_turns_a_into_z():
    assert Cipher("z").encode("a") == "z"


def test_encode_wraps_from_z_to_a():
    assert Cipher("b").encode("z") == "a"


def test_decode_key_wraps_around_when_shorter_than_ciphertext():
    assert Cipher("abcd").decode("hfnoo") == "hello"


def test_decode_single_letter_key_shifts_every_letter_back():
    assert Cipher("dddddd").decode("ldpdsdqgdehdu") == "iamapandabear"


def test_decode_wraps_from_a_to_z():
    assert Cipher("b").decode("a") == "z"


def test_round_trip_with_given_key():
    cipher = Cipher("abcd")
    assert cipher.decode(cipher.encode("hello")) == "hello"


def test_random_key_round_trip_recovers_plaintext():
    cipher = Cipher()
    plaintext = "thequickbrownfoxjumpsoverthelazydog"
    assert cipher.decode(cipher.encode(plaintext)) == plaintext


def test_random_key_encoding_gives_lowercase_letters_of_same_length():
    cipher = Cipher()
    plaintext = "a" * 150
    ciphertext = cipher.encode(plaintext)
    assert len(ciphertext) == len(plaintext)
    assert ciphertext.isalpha()
    assert ciphertext.islower()
