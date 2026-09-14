"""ow_06_verrange — hidden checks, 14. **Never enters a workspace.**

Generated from bank/ow_06_verrange/hidden/*.py by export_bank.py; the
anchor table is in ANCHORS.md beside this file.
"""
import solution


def check_h01_ten_after_nine():
    # anchor_kind: goal
    # anchor: They have been burned by "1.10" sorting before "1.9"
    # derivation: the minor and patch fields are numbers, so a two-digit field is
    # larger than a one-digit field however the text sorts.


    def _bank_entry(solution):
        cases = [("0.10.0", "0.9.0", 1), ("0.0.10", "0.0.9", 1), ("1.11.0", "1.2.0", 1)]
        for a, b, want in cases:
            got = solution.compare(a, b)
            assert got == want, "args=%r got=%r want=%r" % ((a, b), got, want)
    _bank_entry(solution)


def check_h02_release_beats_prerelease():
    # anchor_kind: goal
    # anchor: pre-release builds being treated as newer than the real thing
    # derivation: for the same three numbers the plain release is the newer of the two,
    # whatever the pre-release is called.


    def _bank_entry(solution):
        for pre in ("1.2.3-alpha", "1.2.3-zzz", "1.2.3-9999"):
            got = solution.compare(pre, "1.2.3")
            assert got == -1, "args=%r got=%r want=%r" % ((pre, "1.2.3"), got, -1)
    _bank_entry(solution)


def check_h03_only_three_values():
    # anchor_kind: contract
    # anchor: It returns exactly those three values.
    # derivation: the result is -1, 0 or 1 and nothing else, so a caller may compare it
    # against those literals.


    def _bank_entry(solution):
        pairs = [("1.0.0", "2.0.0"), ("2.0.0", "1.0.0"), ("1.0.0", "1.0.0"),
                 ("1.0.0-a", "1.0.0-b"), ("3.4.5-rc.1", "3.4.5-rc.1")]
        for a, b in pairs:
            got = solution.compare(a, b)
            assert got in (-1, 0, 1), "args=%r got=%r want=%r" % ((a, b), got, "-1, 0 or 1")
            assert isinstance(got, int) and not isinstance(got, bool), (
                "args=%r got=%r want=%r" % ((a, b), type(got).__name__, "int"))
    _bank_entry(solution)


def check_h04_numeric_identifiers_by_value():
    # anchor_kind: goal
    # anchor: rc.2 comes after rc.1
    # derivation: an identifier made of digits is a number, so rc.10 is newer than
    # rc.2 even though the text sorts the other way.


    def _bank_entry(solution):
        got = solution.compare("1.0.0-rc.2", "1.0.0-rc.1")
        assert got == 1, "args=%r got=%r want=%r" % (("1.0.0-rc.2", "1.0.0-rc.1"), got, 1)
        got = solution.compare("1.0.0-rc.10", "1.0.0-rc.2")
        assert got == 1, "args=%r got=%r want=%r" % (("1.0.0-rc.10", "1.0.0-rc.2"), got, 1)
    _bank_entry(solution)


def check_h05_text_identifiers_by_ascii():
    # anchor_kind: goal
    # anchor: alpha comes before beta
    # derivation: identifiers that are not all digits sort the way their characters
    # sort.


    def _bank_entry(solution):
        got = solution.compare("2.1.0-alpha", "2.1.0-beta")
        assert got == -1, "args=%r got=%r want=%r" % (("2.1.0-alpha", "2.1.0-beta"), got, -1)
        got = solution.compare("2.1.0-beta", "2.1.0-rc")
        assert got == -1, "args=%r got=%r want=%r" % (("2.1.0-beta", "2.1.0-rc"), got, -1)
    _bank_entry(solution)


def check_h06_digits_below_text():
    # anchor_kind: contract
    # anchor: an all-digit identifier is older than one that is not
    # derivation: at the same position a numeric identifier loses to a textual one, so
    # 1.0.0-1 is older than 1.0.0-alpha.


    def _bank_entry(solution):
        got = solution.compare("1.0.0-1", "1.0.0-alpha")
        assert got == -1, "args=%r got=%r want=%r" % (("1.0.0-1", "1.0.0-alpha"), got, -1)
        got = solution.compare("1.0.0-rc.5", "1.0.0-rc.beta")
        assert got == -1, "args=%r got=%r want=%r" % (("1.0.0-rc.5", "1.0.0-rc.beta"), got, -1)
    _bank_entry(solution)


def check_h07_longer_prerelease_wins():
    # anchor_kind: goal
    # anchor: a pre-release with more parts is newer than the same pre-release with
    # fewer
    # derivation: when every shared identifier matches, the one carrying an extra
    # identifier is the newer of the two.


    def _bank_entry(solution):
        got = solution.compare("1.0.0-rc.1.2", "1.0.0-rc.1")
        assert got == 1, "args=%r got=%r want=%r" % (("1.0.0-rc.1.2", "1.0.0-rc.1"), got, 1)
        got = solution.compare("1.0.0-alpha", "1.0.0-alpha.1")
        assert got == -1, "args=%r got=%r want=%r" % (("1.0.0-alpha", "1.0.0-alpha.1"), got, -1)
    _bank_entry(solution)


def check_h08_every_condition_holds():
    # anchor_kind: goal
    # anchor: every condition has to hold
    # derivation: a three-condition requirement is only satisfied when all three are
    # true; one failure is enough to answer no.


    def _bank_entry(solution):
        spec = ">=1.0.0,<2.0.0,!=1.5.0"
        assert solution.satisfies("1.4.0", spec) is True, (
            "args=%r got=%r want=%r" % (("1.4.0", spec), solution.satisfies("1.4.0", spec), True))
        assert solution.satisfies("1.5.0", spec) is False, (
            "args=%r got=%r want=%r" % (("1.5.0", spec), solution.satisfies("1.5.0", spec), False))
        assert solution.satisfies("0.9.0", spec) is False, (
            "args=%r got=%r want=%r" % (("0.9.0", spec), solution.satisfies("0.9.0", spec), False))
    _bank_entry(solution)


def check_h09_spaces_around_conditions():
    # anchor_kind: goal
    # anchor: sometimes with spaces around them
    # derivation: padding around a condition is not part of the version, so the spaced
    # requirement answers exactly like the tight one.


    def _bank_entry(solution):
        tight = ">=1.2.0,<1.9.0"
        spaced = " >=1.2.0 ,  <1.9.0 "
        for version in ("1.2.0", "1.5.5", "1.9.0", "1.1.9"):
            got = solution.satisfies(version, spaced)
            want = solution.satisfies(version, tight)
            assert got == want, "args=%r got=%r want=%r" % ((version, spaced), got, want)
        assert solution.satisfies("1.5.5", spaced) is True, (
            "args=%r got=%r want=%r" % (("1.5.5", spaced), solution.satisfies("1.5.5", spaced), True))
    _bank_entry(solution)


def check_h10_all_six_operators():
    # anchor_kind: contract
    # anchor: A condition is one of `>=`, `>`, `<=`, `<`, `==`, `!=` followed by a
    # version.
    # derivation: each operator is checked on both sides of its own boundary, which is
    # also where a solution that matches ">" before ">=" goes wrong.


    def _bank_entry(solution):
        cases = [("1.0.0", ">0.9.9", True), ("1.0.0", ">1.0.0", False),
                 ("1.0.0", ">=1.0.0", True), ("1.0.0", ">=1.0.1", False),
                 ("1.0.0", "<1.0.1", True), ("1.0.0", "<1.0.0", False),
                 ("1.0.0", "<=1.0.0", True), ("1.0.0", "<=0.9.9", False),
                 ("1.0.0", "==1.0.0", True), ("1.0.0", "==1.0.1", False),
                 ("1.0.0", "!=1.0.1", True), ("1.0.0", "!=1.0.0", False)]
        for version, spec, want in cases:
            got = solution.satisfies(version, spec)
            assert got is want, "args=%r got=%r want=%r" % ((version, spec), got, want)
    _bank_entry(solution)


def check_h11_prerelease_in_a_spec():
    # anchor_kind: contract
    # anchor: Every condition has to hold for `satisfies` to return True.
    # derivation: the comparison used inside a condition is the same one `compare`
    # implements, so a pre-release bound behaves the same way there.


    def _bank_entry(solution):
        assert solution.satisfies("1.0.0-rc.2", ">=1.0.0-rc.1") is True, (
            "args=%r got=%r want=%r" % (("1.0.0-rc.2", ">=1.0.0-rc.1"), False, True))
        assert solution.satisfies("1.0.0-rc.2", ">=1.0.0") is False, (
            "args=%r got=%r want=%r" % (("1.0.0-rc.2", ">=1.0.0"), True, False))
        assert solution.satisfies("1.0.0", ">1.0.0-rc.9") is True, (
            "args=%r got=%r want=%r" % (("1.0.0", ">1.0.0-rc.9"), False, True))
    _bank_entry(solution)


def check_h12_bad_version_rejected():
    # anchor_kind: goal
    # anchor: A version string or a requirement they cannot make sense of has to be
    # rejected rather than guessed at
    # derivation: a version that is not three numbers with an optional pre-release
    # raises from both entry points instead of comparing as something.


    def _bank_entry(solution):
        for text in ("1.2", "1.2.3.4", "v1.2.3", "1.2.x", "", "1.2.3-"):
            try:
                solution.compare(text, "1.0.0")
            except ValueError:
                pass
            else:
                raise AssertionError("args=%r got=%r want=%r" % (text, "compared fine", "ValueError"))
            try:
                solution.satisfies(text, ">=1.0.0")
            except ValueError:
                continue
            raise AssertionError("args=%r got=%r want=%r" % (text, "answered fine", "ValueError"))
    _bank_entry(solution)


def check_h13_bad_spec_rejected():
    # anchor_kind: contract
    # anchor: a spec with an empty condition, and a condition with an unrecognised
    # operator all raise `ValueError`
    # derivation: a requirement whose operator is not one of the six, or that contains
    # an empty piece, is rejected rather than silently answered.


    def _bank_entry(solution):
        for spec in ("~>1.0.0", "1.0.0", ">=1.0.0,", "", ">=1.0.0,,<2.0.0", "=>1.0.0"):
            try:
                solution.satisfies("1.5.0", spec)
            except ValueError:
                continue
            raise AssertionError("args=%r got=%r want=%r" % (spec, "answered fine", "ValueError"))
    _bank_entry(solution)


def check_h14_bad_target_version_rejected():
    # anchor_kind: goal
    # anchor: because a silent guess is how a bad build shipped last time
    # derivation: the version written inside a condition goes through the same check as
    # the version being tested, so a typo there is an error and not a False.


    def _bank_entry(solution):
        for spec in (">=1.0", "<2.0.0.0", "==one.two.three"):
            try:
                solution.satisfies("1.5.0", spec)
            except ValueError:
                continue
            raise AssertionError("args=%r got=%r want=%r" % (spec, "answered fine", "ValueError"))
    _bank_entry(solution)
