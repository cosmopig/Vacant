from series import slices
import pytest


# SRC: "Given a string of digits, output all the contiguous substrings of length `n` in that string in the order that they appear."
assert slices("49142", 3) == ["491", "914", "142"]

# SRC: "And the following 4-digit series:"
assert slices("49142", 4) == ["4914", "9142"]

# SRC: "Given a string of digits, output all the contiguous substrings of length `n` in that string in the order that they appear."
assert slices("49142", 5) == ["49142"]

# SRC: "Given a string of digits, output all the contiguous substrings of length `n` in that string in the order that they appear."
assert slices("0123", 1) == ["0", "1", "2", "3"]

# SRC: "Given a string of digits, output all the contiguous substrings of length `n` in that string in the order that they appear."
assert slices("0123", 2) == ["01", "12", "23"]

# SRC: "the digits need not be _numerically consecutive_."
assert slices("13579", 2) == ["13", "35", "57", "79"]

# SRC: "Note that these series are only required to occupy _adjacent positions_ in the input;"
assert slices("1212", 2) == ["12", "21", "12"]


# SRC: "if the series and/or length parameters input into the `slice()` function are empty or out of range."
with pytest.raises(ValueError, match=r".+"):
    slices("", 1)

# SRC: "if the slice length is zero."
with pytest.raises(ValueError, match=r".+"):
    slices("49142", 0)

# SRC: "if the slice length is negative."
with pytest.raises(ValueError, match=r".+"):
    slices("49142", -1)

# SRC: "if the slice length is longer than the series."
with pytest.raises(ValueError, match=r".+"):
    slices("49142", 6)

# SRC: "The tests will only pass if you both `raise` the `exception` and include a message with it."
with pytest.raises(ValueError, match=r".+"):
    slices("", 0)
