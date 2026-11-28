import string

from simple_cipher import Cipher

LOWER = set(string.ascii_lowercase)


def test_encode_and_decode_return_str():
    """REQ: "Converting plaintext to ciphertext is called _encoding_ while the reverse is called _decoding_."

    encode and decode take text and return text (str), with or without an explicit key.
    """
    assert isinstance(Cipher("abcd").encode("hello"), str)
    assert isinstance(Cipher("abcd").decode("hfnoo"), str)
    assert isinstance(Cipher(key="abcd").encode("hello"), str)
    assert isinstance(Cipher().encode("hello"), str)


def test_example_iamapandabear_with_single_letter_key():
    """REQ: "For example, the plaintext `"iamapandabear"` would become `"ldpdsdqgdehdu"`."

    A key made of one repeated letter shifts every letter by the same amount.
    """
    assert Cipher("dddddd").encode("iamapandabear") == "ldpdsdqgdehdu"


def test_example_hello_with_abcd_key():
    """REQ: "Applying those shifts to the letters of `"hello"` we get `"hfnoo"`."

    Shifts 0, 1, 2, 3, 0 applied to h, e, l, l, o.
    """
    assert Cipher("abcd").encode("hello") == "hfnoo"


def test_key_of_only_a_leaves_text_unchanged():
    """REQ: "If the key only contains the letter `"a"` (one or more times), the shift distance is zero and the ciphertext is the same as the plaintext."

    A key made only of 'a' (one or more times) is an identity transformation.
    """
    assert Cipher("a").encode("iamapandabear") == "iamapandabear"
    assert Cipher("aaaa").encode("hello") == "hello"
    assert Cipher("aaaaaaaaaaaaaaaa").encode("hello") == "hello"


def test_key_wraps_around_for_longer_text():
    """REQ: "If you run out of letters in the key before you run out of letters in the plaintext, start over from the start of the key again."

    With key "abcd" the shifts for "hellohello" are 0,1,2,3,0,1,2,3,0,1.
    """
    assert Cipher("abcd").encode("hellohello") == "hfnooigolp"


def test_single_letter_key_is_a_caesar_shift():
    """REQ: "If the key only contains one letter, such as `"dddddd"`, then all letters of the plaintext are shifted by the same amount (three in this example), which would make this the same as a rotational cipher or shift cipher (sometimes called a Caesar cipher)."

    Key "c" shifts every letter by 2, wrapping past 'z' back to 'a'.
    """
    assert Cipher("c").encode("xyz") == "zab"
    assert Cipher("ccc").encode("xyz") == "zab"


def test_decode_examples():
    """REQ: "The unencrypted string is called the _plaintext_ and the encrypted string is called the _ciphertext_."

    Decoding reverses the shifts for the examples given in the text.
    """
    assert Cipher("dddddd").decode("ldpdsdqgdehdu") == "iamapandabear"
    assert Cipher("abcd").decode("hfnoo") == "hello"
    assert Cipher("abcd").decode("hfnooigolp") == "hellohello"


def test_decode_inverts_encode():
    """REQ: "Converting plaintext to ciphertext is called _encoding_ while the reverse is called _decoding_."

    For any key and plaintext, decoding the ciphertext gives back the plaintext.
    """
    keys = ["abcd", "dddddd", "lemon", "a", "zzzz"]
    texts = ["hello", "iamapandabear", "thequickbrownfoxjumpsoverthelazydog", ""]
    for key in keys:
        for text in texts:
            cipher = Cipher(key)
            assert cipher.decode(cipher.encode(text)) == text, (key, text)


def test_ciphertext_has_same_length_as_plaintext():
    """REQ: "In a _substitution cipher_, each plaintext letter is replaced with a ciphertext letter which is computed with the help of a _key_."

    Each plaintext letter is replaced by exactly one ciphertext letter.
    """
    for key in ["abcd", "dddddd", "lemon", "a"]:
        for text in ["hello", "iamapandabear", "thequickbrownfoxjumpsoverthelazydog"]:
            assert len(Cipher(key).encode(text)) == len(text), (key, text)


def test_empty_plaintext_gives_empty_ciphertext():
    """REQ: "In a _substitution cipher_, each plaintext letter is replaced with a ciphertext letter which is computed with the help of a _key_."

    With no letters to replace, the output is the empty string, and likewise for decoding.
    """
    assert Cipher("abc").encode("") == ""
    assert Cipher("abc").decode("") == ""


def test_encoding_is_deterministic_for_a_given_key():
    """REQ: "Each letter of the plaintext is _shifted_ or _rotated_ by a distance based on a corresponding letter in the key."

    The same key and plaintext always produce the same ciphertext.
    """
    text = "attackatdawn"
    c1 = Cipher("lemon")
    c2 = Cipher("lemon")
    first = c1.encode(text)
    assert c1.encode(text) == first
    assert c2.encode(text) == first


def test_output_uses_only_lowercase_letters():
    """REQ: "In this cipher, the key is a series of lowercase letters, such as `"abcd"`."

    Shifting lowercase letters within the alphabet keeps them lowercase letters.
    """
    text = "thequickbrownfoxjumpsoverthelazydog"
    for key in ["abcd", "lemon", "zzzz", "dddddd"]:
        assert set(Cipher(key).encode(text)) <= LOWER, key


def test_shift_by_one_and_wrap_from_z_to_a():
    """REQ: "A `"b"` in the key means a shift of 1."

    Key "b" moves 'z' to 'a', and key "z" (shift 25) moves 'a' to 'z' and 'z' to 'y'.
    """
    assert Cipher("b").encode("z") == "a"
    assert Cipher("b").decode("a") == "z"
    assert Cipher("z").encode("a") == "z"
    assert Cipher("z").encode("z") == "y"


def test_default_key_is_at_least_100_random_lowercase_letters():
    """REQ: "If no key is provided, generate a key which consists of at least 100 random lowercase letters from the Latin alphabet."

    Encoding a long run of 'a' exposes the key itself, since 'a' shifted by k gives the k-th key letter.
    The exposed key must be lowercase letters and must not repeat with any period shorter than 100.
    """
    out = Cipher().encode("a" * 300)
    assert len(out) == 300
    assert set(out) <= LOWER
    assert len(set(out)) > 1
    for period in range(1, 100):
        assert out[period:] != out[:-period], (
            "key appears to repeat with period " + str(period) + ", so it is shorter than 100"
        )


def test_default_keys_differ_between_instances():
    """REQ: "If no key is provided, generate a key which consists of at least 100 random lowercase letters from the Latin alphabet."

    Keys are random, so two cipher objects created without a key should not share the same key.
    """
    a = Cipher().encode("a" * 100)
    b = Cipher().encode("a" * 100)
    assert a != b


def test_default_key_round_trips():
    """REQ: "If no key is provided, generate a key which consists of at least 100 random lowercase letters from the Latin alphabet."

    A cipher created without a key can still encode and decode consistently.
    """
    cipher = Cipher()
    text = "thequickbrownfoxjumpsoverthelazydog"
    assert cipher.decode(cipher.encode(text)) == text
