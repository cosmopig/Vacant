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
