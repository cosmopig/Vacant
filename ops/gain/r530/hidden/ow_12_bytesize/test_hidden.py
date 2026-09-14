"""ow_12_bytesize — hidden checks, 13. **Never enters a workspace.**

Generated from bank/ow_12_bytesize/hidden/*.py by export_bank.py; the
anchor table is in ANCHORS.md beside this file.
"""
import solution


def check_h01_two_meanings_of_kb():
    # anchor_kind: goal
    # anchor: the two meanings of "KB"
    # derivation: the i spelling steps by 1024 and the plain spelling by 1000, so the
    # same number with the two spellings gives two different byte counts.


    def _bank_entry(solution):
        pairs = [("1 KiB", 1024, "1 KB", 1000),
                 ("1 MiB", 1024 ** 2, "1 MB", 1000 ** 2),
                 ("2 GiB", 2 * 1024 ** 3, "2 GB", 2 * 1000 ** 3),
                 ("1 TiB", 1024 ** 4, "1 TB", 1000 ** 4)]
        for binary_text, binary_want, decimal_text, decimal_want in pairs:
            got = solution.to_bytes(binary_text)
            assert got == binary_want, "args=%r got=%r want=%r" % (binary_text, got, binary_want)
            got = solution.to_bytes(decimal_text)
            assert got == decimal_want, "args=%r got=%r want=%r" % (decimal_text, got, decimal_want)
    _bank_entry(solution)


def check_h02_unit_case_does_not_matter():
    # anchor_kind: goal
    # anchor: People write the unit in whatever case they feel like
    # derivation: every casing of a unit reads as the same unit.


    def _bank_entry(solution):
        for text in ("1 kib", "1 KIB", "1 KiB", "1 kIb"):
            got = solution.to_bytes(text)
            assert got == 1024, "args=%r got=%r want=%r" % (text, got, 1024)
        for text in ("2 mb", "2 MB", "2 Mb"):
            got = solution.to_bytes(text)
            assert got == 2000000, "args=%r got=%r want=%r" % (text, got, 2000000)
    _bank_entry(solution)


def check_h03_space_is_optional():
    # anchor_kind: goal
    # anchor: sometimes leave a space before it and sometimes not
    # derivation: none, one or several spaces between the number and the unit all read
    # the same, and padding around the whole string is ignored.


    def _bank_entry(solution):
        for text in ("4KiB", "4 KiB", "4    KiB", "  4KiB  ", "\t4 KiB\n"):
            got = solution.to_bytes(text)
            assert got == 4096, "args=%r got=%r want=%r" % (text, got, 4096)
    _bank_entry(solution)


def check_h04_no_unit_is_bytes():
    # anchor_kind: goal
    # anchor: A size with no unit at all is a count of bytes.
    # derivation: a bare number and the same number with the byte unit in either case
    # all mean the same thing.


    def _bank_entry(solution):
        for text in ("777", "777B", "777 b", "777 B"):
            got = solution.to_bytes(text)
            assert got == 777, "args=%r got=%r want=%r" % (text, got, 777)
    _bank_entry(solution)


def check_h05_fraction_is_dropped():
    # anchor_kind: goal
    # anchor: the fraction is dropped rather than rounded up
    # derivation: a value whose product has a fraction truncates downward, so 2.9
    # bytes is 2 bytes and not 3.


    def _bank_entry(solution):
        cases = [("2.9", 2), ("0.9 B", 0), ("1.75 KiB", 1792), ("0.0009 KB", 0)]
        for text, want in cases:
            got = solution.to_bytes(text)
            assert got == want, "args=%r got=%r want=%r" % (text, got, want)
    _bank_entry(solution)


def check_h06_largest_unit_below_the_step():
    # anchor_kind: contract
    # anchor: The unit chosen is the largest one that leaves the number below the step
    # derivation: each size lands in the unit whose number is at least 1 and less than
    # the step, on both sides of every boundary.


    def _bank_entry(solution):
        cases = [(1023, "1023 B"), (1024, "1.0 KiB"), (1024 ** 2 - 1, "1024.0 KiB"),
                 (1024 ** 2, "1.0 MiB"), (1024 ** 3, "1.0 GiB")]
        for number, want in cases:
            got = solution.humanize(number)
            assert got == want, "args=%r got=%r want=%r" % (number, got, want)
    _bank_entry(solution)


def check_h07_trailing_zero_is_kept():
    # anchor_kind: goal
    # anchor: keep one decimal place even when it is a round number
    # derivation: a size that lands on a whole number of units still shows the decimal
    # point and the zero after it.


    def _bank_entry(solution):
        cases = [(1024, "1.0 KiB"), (2 * 1024 ** 2, "2.0 MiB"), (10 * 1024 ** 3, "10.0 GiB")]
        for number, want in cases:
            got = solution.humanize(number)
            assert got == want, "args=%r got=%r want=%r" % (number, got, want)
    _bank_entry(solution)


def check_h08_bytes_are_whole_things():
    # anchor_kind: goal
    # anchor: except for plain bytes, which are whole things and should look like it
    # derivation: anything below one step prints as an integer with the byte unit and
    # no decimal point anywhere.


    def _bank_entry(solution):
        for number in (0, 1, 7, 512, 999, 1023):
            got = solution.humanize(number)
            assert got == "%d B" % number, "args=%r got=%r want=%r" % (number, got, "%d B" % number)
            assert "." not in got, "args=%r got=%r want=%r" % (number, got, "no decimal point")
    _bank_entry(solution)


def check_h09_decimal_family():
    # anchor_kind: contract
    # anchor: It uses the 1024 units when `binary` is true and the 1000 units otherwise.
    # derivation: with the flag turned off the steps are thousands and the unit names
    # lose the i.


    def _bank_entry(solution):
        cases = [(999, "999 B"), (1000, "1.0 KB"), (1500, "1.5 KB"),
                 (2 * 1000 ** 3, "2.0 GB"), (1000 ** 4, "1.0 TB")]
        for number, want in cases:
            got = solution.humanize(number, binary=False)
            assert got == want, "args=%r got=%r want=%r" % ((number, False), got, want)
    _bank_entry(solution)


def check_h10_above_the_largest_unit():
    # anchor_kind: goal
    # anchor: Sizes larger than the biggest unit they use should still print, rather
    # than falling back to a bare byte count.
    # derivation: beyond a terabyte the unit stops changing and the number grows past
    # the step instead.


    def _bank_entry(solution):
        got = solution.humanize(2048 * 1024 ** 4)
        assert got == "2048.0 TiB", "args=%r got=%r want=%r" % (2048 * 1024 ** 4, got, "2048.0 TiB")
        got = solution.humanize(5000 * 1000 ** 4, binary=False)
        assert got == "5000.0 TB", "args=%r got=%r want=%r" % (5000 * 1000 ** 4, got, "5000.0 TB")
    _bank_entry(solution)


def check_h11_round_trip():
    # anchor_kind: goal
    # anchor: numbers that come back out different from the way they went in
    # derivation: for a size the printed form represents exactly, reading it back gives
    # the number that was printed.


    def _bank_entry(solution):
        for number in (0, 512, 1024, 1536, 5 * 1024 ** 2, 3 * 1024 ** 3):
            printed = solution.humanize(number)
            got = solution.to_bytes(printed)
            assert got == number, "args=%r got=%r want=%r" % (printed, got, number)
        for number in (999, 1000, 1500, 2 * 1000 ** 3):
            printed = solution.humanize(number, binary=False)
            got = solution.to_bytes(printed)
            assert got == number, "args=%r got=%r want=%r" % (printed, got, number)
    _bank_entry(solution)


def check_h12_negative_is_refused():
    # anchor_kind: goal
    # anchor: a negative size
    # derivation: a minus sign is refused when reading and when printing, rather than
    # producing a negative byte count.


    def _bank_entry(solution):
        for text in ("-1", "-1 KiB", "- 5 MB"):
            try:
                solution.to_bytes(text)
            except ValueError:
                continue
            raise AssertionError("args=%r got=%r want=%r" % (text, "a number", "ValueError"))
        for number in (-1, -1024):
            try:
                solution.humanize(number)
            except ValueError:
                continue
            raise AssertionError("args=%r got=%r want=%r" % (number, "a string", "ValueError"))
    _bank_entry(solution)


def check_h13_other_refusals():
    # anchor_kind: goal
    # anchor: an empty setting, a unit nobody has heard of, two units in one string
    # derivation: each named refusal is checked on its own, including a string that has
    # a unit but no number.


    def _bank_entry(solution):
        for text in ("", "  ", "KiB", "12 XB", "3 KiB MB", "1 2 KiB", "1,5 KiB", "1e3"):
            try:
                solution.to_bytes(text)
            except ValueError:
                continue
            raise AssertionError("args=%r got=%r want=%r" % (text, "a number", "ValueError"))
    _bank_entry(solution)
