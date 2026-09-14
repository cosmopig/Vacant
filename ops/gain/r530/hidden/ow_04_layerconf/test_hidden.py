"""ow_04_layerconf — hidden checks, 15. **Never enters a workspace.**

Generated from bank/ow_04_layerconf/hidden/*.py by export_bank.py; the
anchor table is in ANCHORS.md beside this file.
"""
import solution


def check_h01_env_beats_file():
    # anchor_kind: contract
    # anchor: Precedence is env over file over default.
    # derivation: when all three name the same setting the environment value is the one
    # that survives.


    def _bank_entry(solution):
        defaults = {"level": "info"}
        file_text = "level = debug\n"
        env = {"APP_LEVEL": "warn"}
        config = solution.load(defaults, file_text, env)
        got = config.get("level")
        assert got == "warn", "args=%r got=%r want=%r" % ((file_text, env), got, "warn")
    _bank_entry(solution)


def check_h02_file_beats_default():
    # anchor_kind: contract
    # anchor: Precedence is env over file over default.
    # derivation: with no environment variable in play the file still has to beat the
    # baked-in value.


    def _bank_entry(solution):
        defaults = {"timeout": 30}
        file_text = "timeout = 5\n"
        config = solution.load(defaults, file_text, {})
        got = (config.get("timeout"), config.source("timeout"))
        assert got == (5, "file"), "args=%r got=%r want=%r" % (file_text, got, (5, "file"))
    _bank_entry(solution)


def check_h03_sections_make_dotted_keys():
    # anchor_kind: goal
    # anchor: Their settings file is grouped into sections
    # derivation: a key under [db] is the setting db.something, and a key written
    # before any section header stays at the top level.


    def _bank_entry(solution):
        defaults = {"name": "svc", "db.host": "127.0.0.1", "db.port": 5432, "log.path": "/tmp/l"}
        file_text = "name = billing\n[db]\nhost = db.internal\nport = 6000\n[log]\npath = /var/log/b\n"
        config = solution.load(defaults, file_text, {})
        got = config.as_dict()
        want = {"name": "billing", "db.host": "db.internal", "db.port": 6000, "log.path": "/var/log/b"}
        assert got == want, "args=%r got=%r want=%r" % (file_text, got, want)
    _bank_entry(solution)


def check_h04_comments_and_blanks():
    # anchor_kind: goal
    # anchor: half of it is comments
    # derivation: comment lines and blank lines carry no setting, and a comment sitting
    # above a key must not swallow it.


    def _bank_entry(solution):
        defaults = {"a": 1, "b": 2}
        file_text = "# a is the first one\n\n   # indented comment\na = 10\n\nb = 20\n"
        config = solution.load(defaults, file_text, {})
        got = config.as_dict()
        want = {"a": 10, "b": 20}
        assert got == want, "args=%r got=%r want=%r" % (file_text, got, want)
    _bank_entry(solution)


def check_h05_boolean_spellings():
    # anchor_kind: contract
    # anchor: A `bool` accepts `true`, `false`, `1`, `0`, `yes` and `no` without regard
    # to case.
    # derivation: all six words, in mixed case, have to land on the right boolean.


    def _bank_entry(solution):
        defaults = {"flag": False}
        truthy = ("true", "TRUE", "1", "yes", "Yes")
        falsy = ("false", "False", "0", "no", "NO")
        for word in truthy:
            got = solution.load(defaults, "flag = %s\n" % word, {}).get("flag")
            assert got is True, "args=%r got=%r want=%r" % (word, got, True)
        for word in falsy:
            got = solution.load(defaults, "flag = %s\n" % word, {}).get("flag")
            assert got is False, "args=%r got=%r want=%r" % (word, got, False)
    _bank_entry(solution)


def check_h06_unconvertible_boolean():
    # anchor_kind: goal
    # anchor: a value that cannot be turned into the right kind of thing must fail
    # loudly rather than becoming a zero
    # derivation: a word that is not one of the accepted boolean spellings must raise
    # rather than quietly become False.


    def _bank_entry(solution):
        defaults = {"flag": True}
        file_text = "flag = maybe\n"
        try:
            solution.load(defaults, file_text, {})
        except ValueError:
            return
        raise AssertionError("args=%r got=%r want=%r" % (file_text, "no error", "ValueError"))
    _bank_entry(solution)


def check_h07_unconvertible_number():
    # anchor_kind: contract
    # anchor: A value that cannot be converted raises `ValueError`.
    # derivation: a word where an integer is expected is a ValueError, from the file
    # layer and from the environment layer alike.


    def _bank_entry(solution):
        defaults = {"port": 80}
        try:
            solution.load(defaults, "port = eighty\n", {})
        except ValueError:
            pass
        else:
            raise AssertionError("args=%r got=%r want=%r" % ("port = eighty", "no error", "ValueError"))

        try:
            solution.load(defaults, None, {"APP_PORT": "eighty"})
        except ValueError:
            return
        raise AssertionError("args=%r got=%r want=%r" % ({"APP_PORT": "eighty"}, "no error", "ValueError"))
    _bank_entry(solution)


def check_h08_env_name_shape():
    # anchor_kind: contract
    # anchor: After the prefix, `__` stands for `.` and the rest is lowercased, so
    # `APP_DB__PORT` sets `db.port`.
    # derivation: the capitals-and-underscores spelling has to map onto the dotted key,
    # and the prefix itself is matched without regard to case.


    def _bank_entry(solution):
        defaults = {"db.port": 5432, "db.pool.size": 4}
        env = {"APP_DB__PORT": "6543", "app_db__pool__size": "16"}
        config = solution.load(defaults, None, env)
        got = config.as_dict()
        want = {"db.port": 6543, "db.pool.size": 16}
        assert got == want, "args=%r got=%r want=%r" % (env, got, want)
    _bank_entry(solution)


def check_h09_unrelated_env_ignored():
    # anchor_kind: goal
    # anchor: most of which have nothing to do with this program
    # derivation: environment variables without the prefix must not touch the settings,
    # even when their name after stripping would have matched.


    def _bank_entry(solution):
        defaults = {"port": 80, "home": "/srv"}
        env = {"PORT": "9999", "HOME": "/root", "PATH": "/bin", "APP_PORT": "8081"}
        config = solution.load(defaults, None, env)
        got = config.as_dict()
        want = {"port": 8081, "home": "/srv"}
        assert got == want, "args=%r got=%r want=%r" % (env, got, want)
        assert config.source("home") == "default", (
            "args=%r got=%r want=%r" % (env, config.source("home"), "default"))
    _bank_entry(solution)


def check_h10_unknown_keys_ignored():
    # anchor_kind: goal
    # anchor: A typo in a setting name should be ignored rather than quietly adding a
    # setting nobody reads
    # derivation: a misspelled key in the file or the environment changes nothing and
    # never appears in the returned settings.


    def _bank_entry(solution):
        defaults = {"retries": 3}
        file_text = "retires = 9\nretries = 4\n"
        env = {"APP_RETRYS": "77"}
        config = solution.load(defaults, file_text, env)
        got = config.as_dict()
        want = {"retries": 4}
        assert got == want, "args=%r got=%r want=%r" % ((file_text, env), got, want)
    _bank_entry(solution)


def check_h11_unknown_key_raises():
    # anchor_kind: contract
    # anchor: `get` and `source` raise `KeyError` for a key that is not in `defaults`.
    # derivation: asking about a setting that does not exist is a mistake worth
    # reporting, not a None.


    def _bank_entry(solution):
        config = solution.load({"a": 1}, None, {})
        for method in ("get", "source"):
            try:
                getattr(config, method)("nope")
            except KeyError:
                continue
            raise AssertionError("args=%r got=%r want=%r" % (method + "('nope')", "no error", "KeyError"))
    _bank_entry(solution)


def check_h12_no_file_at_all():
    # anchor_kind: goal
    # anchor: Sometimes there is no settings file at all.
    # derivation: passing None for the file must behave exactly like passing an empty
    # one, with the environment still applied on top.


    def _bank_entry(solution):
        defaults = {"a": 1, "b": "x"}
        env = {"APP_B": "y"}
        none_config = solution.load(defaults, None, env)
        empty_config = solution.load(defaults, "", env)
        got = (none_config.as_dict(), none_config.source("a"))
        want = ({"a": 1, "b": "y"}, "default")
        assert got == want, "args=%r got=%r want=%r" % (env, got, want)
        assert none_config.as_dict() == empty_config.as_dict(), (
            "args=%r got=%r want=%r" % (env, none_config.as_dict(), empty_config.as_dict()))
    _bank_entry(solution)


def check_h13_value_with_equals_sign():
    # anchor_kind: goal
    # anchor: Some of their values contain an equals sign.
    # derivation: only the first equals sign separates the key from the value, so the
    # rest of the line arrives intact.


    def _bank_entry(solution):
        defaults = {"dsn": ""}
        file_text = "dsn = postgres://u:p@h/db?sslmode=require&x=1\n"
        got = solution.load(defaults, file_text, {}).get("dsn")
        want = "postgres://u:p@h/db?sslmode=require&x=1"
        assert got == want, "args=%r got=%r want=%r" % (file_text, got, want)
    _bank_entry(solution)


def check_h14_whitespace_and_stray_lines():
    # anchor_kind: contract
    # anchor: A line that is neither of those and contains no `=` is ignored. The value
    # is everything after the first `=`, with surrounding whitespace removed.
    # derivation: padding around the key and the value disappears, and a junk line with
    # no equals sign does not derail the rest of the file.


    def _bank_entry(solution):
        defaults = {"a": "1", "b": 2}
        file_text = "   a    =    hello   \nthis line is junk\n\tb\t=\t7\t\n"
        got = solution.load(defaults, file_text, {}).as_dict()
        want = {"a": "hello", "b": 7}
        assert got == want, "args=%r got=%r want=%r" % (file_text, got, want)
    _bank_entry(solution)


def check_h15_defaults_fix_the_key_set():
    # anchor_kind: contract
    # anchor: `defaults` fixes both the set of keys and the type of each value.
    # derivation: as_dict() has exactly the default keys, no more and no fewer, and a
    # value's type follows the default even when the file offers something else.


    def _bank_entry(solution):
        defaults = {"n": 0, "s": "", "f": 0.0, "b": False}
        file_text = "n = 5\ns = 5\nf = 5\nb = 1\nextra = 5\n"
        got = solution.load(defaults, file_text, {"APP_ALSO_EXTRA": "5"}).as_dict()
        assert sorted(got) == ["b", "f", "n", "s"], (
            "args=%r got=%r want=%r" % (file_text, sorted(got), ["b", "f", "n", "s"]))
        kinds = [type(got[k]).__name__ for k in ("n", "s", "f", "b")]
        want = ["int", "str", "float", "bool"]
        assert kinds == want, "args=%r got=%r want=%r" % (file_text, kinds, want)
    _bank_entry(solution)
