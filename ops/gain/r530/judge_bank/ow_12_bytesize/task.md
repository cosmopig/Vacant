# Goal

A client's config files and log lines are full of sizes written the way humans
write them, and elsewhere the same sizes are printed back out for humans to read.
They keep getting bitten by the two meanings of "KB" and by numbers that come back
out different from the way they went in.

People write the unit in whatever case they feel like, and sometimes leave a space
before it and sometimes not. A size with no unit at all is a count of bytes.

They want the printed form to keep one decimal place even when it is a round
number, except for plain bytes, which are whole things and should look like it.
Sizes larger than the biggest unit they use should still print, rather than
falling back to a bare byte count.

A fractional byte count is not a thing, so the fraction is dropped rather than
rounded up. Anything they cannot read has to be refused rather than guessed at: an
empty setting, a unit nobody has heard of, two units in one string, a negative
size.

# Contract

    solution.to_bytes(s: str) -> int
    solution.humanize(n: int, *, binary: bool = True) -> str

- `to_bytes` reads strings such as `"1.5 KiB"`, `"10MB"`, `"512"` and `"3 b"`.
  Surrounding whitespace is ignored, and any amount of whitespace may sit between
  the number and the unit, including none.
- The number is one or more digits with at most one dot and at least one digit
  after it if the dot is there. Nothing else is a number.
- Units are matched without regard to case. `KiB`, `MiB`, `GiB` and `TiB` step by
  1024; `KB`, `MB`, `GB` and `TB` step by 1000; `B` or no unit at all means bytes.
- The result is the number multiplied by the unit's step, with the fraction
  dropped -- truncated toward zero, never rounded up.
- `humanize` returns the number, one space, and the unit. It uses the 1024 units
  when `binary` is true and the 1000 units otherwise.
- The unit chosen is the largest one that leaves the number below the step, except
  that `TiB` and `TB` are the largest units there are: above them the number simply
  keeps growing.
- The number is printed to one decimal place, keeping a trailing `.0`. When the
  size is below one step it is printed as a whole number of bytes with the unit
  `B`, so `512` gives `"512 B"` and `1024` gives `"1.0 KiB"`.
- `ValueError` is raised for an empty string, a string that is not a number
  followed by an optional unit, an unrecognised unit, more than one unit, and a
  negative size given to either function.
