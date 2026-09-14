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
