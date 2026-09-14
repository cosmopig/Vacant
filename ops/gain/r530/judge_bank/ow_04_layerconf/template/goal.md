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
