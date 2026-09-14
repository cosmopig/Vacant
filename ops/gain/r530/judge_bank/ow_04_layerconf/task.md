# Goal

A client's program takes settings from three places: values baked into the
program, a settings file, and environment variables. They keep losing track of
which one actually won, and things break when a number arrives as a string. They
want something that hands back the final settings and can also answer, for any
single setting, where that value came from.

Their settings file is grouped into sections and half of it is comments. Some of
their values contain an equals sign. Sometimes there is no settings file at all.

Their deployment sets a pile of environment variables, most of which have nothing
to do with this program, and the ones that do are spelled in capitals with
underscores rather than in the dotted form the program uses.

A typo in a setting name should be ignored rather than quietly adding a setting
nobody reads, and a value that cannot be turned into the right kind of thing must
fail loudly rather than becoming a zero.

# Contract

    solution.load(defaults: dict, file_text: str | None, env: dict) -> Config
    Config.get(key: str) -> object
    Config.source(key: str) -> str            # "default" | "file" | "env"
    Config.as_dict() -> dict

- Precedence is env over file over default.
- `defaults` fixes both the set of keys and the type of each value. A key that is
  not in `defaults` is ignored wherever it appears and never shows up in
  `as_dict()`.
- `get` and `source` raise `KeyError` for a key that is not in `defaults`.
- File format: one `key = value` per line. A line whose first non-blank character
  is `#` is a comment and a blank line is nothing. A line of the form `[name]`
  opens a section, and every key after it becomes `name.key` until the next
  section header. A line that is neither of those and contains no `=` is ignored.
  The value is everything after the first `=`, with surrounding whitespace
  removed. `file_text` may be `None`, which means there is no file.
- Environment format: only names beginning with `APP_` are considered, and the
  name is matched without regard to case. After the prefix, `__` stands for `.`
  and the rest is lowercased, so `APP_DB__PORT` sets `db.port`.
- A value arriving from the file or the environment is converted to the type that
  key has in `defaults`: `bool`, `int`, `float` or `str`. A `bool` accepts
  `true`, `false`, `1`, `0`, `yes` and `no` without regard to case.
- A value that cannot be converted raises `ValueError`.
