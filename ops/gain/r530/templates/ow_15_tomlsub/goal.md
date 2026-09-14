# Goal

A client keeps their service settings in a small text format that looks like TOML
but is only the part of it they actually use. They need to read those files into
ordinary Python data, and to write the data back out so that a person can still
edit it by hand afterwards.

The values they use are text, whole numbers, decimals, true and false, and lists of
one of those. A list that mixes kinds is a mistake. Settings are grouped under
headings, and headings can be nested with dots.

Half of every file is comments, and a `#` inside a piece of text is not a comment.
Text sometimes has to contain quotes, tabs and line breaks, written with a
backslash.

The same setting written twice in one group, or the same heading opened twice, is a
mistake they want caught. Every mistake has to say which line it is on, because
these files are edited by hand and the file is the only thing they can look at.

Writing the data out and reading it back has to give the same data, and writing out
what was just read has to give the same text, so the format can sit in version
control without churning.
