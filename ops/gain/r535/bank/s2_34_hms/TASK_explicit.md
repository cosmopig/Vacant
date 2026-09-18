# Task

`hms(seconds)` writes a whole number of seconds as a clock-style
label with colons between the parts.

The labels sit under a progress bar for clips that are usually under a minute
but occasionally run for hours, and the bar is narrow. The number arrives as
the difference between two timestamps that are not guaranteed to be in
order.

## Details

- the hours part is left out when it is zero;
- minutes and seconds always take two digits;
- a negative input raises ValueError.

Write the code in a file called `solution.py` in this directory.
Nothing else is needed and nothing else is read.
