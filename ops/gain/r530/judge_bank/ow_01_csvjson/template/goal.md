# Goal

A client keeps a pile of CSV files that people edit by hand. They want to feed
that data into another tool that only speaks JSON Lines, so they need a command
that turns one CSV file into one JSON object per row.

Their files are messy in the ways hand-edited files are messy: fields containing
commas, fields containing line breaks, quotes inside quoted fields, whole columns
left blank, the same column name used twice, and line endings from whichever
machine last touched the file. Some of the data is not ASCII and has to survive
the trip unchanged.

When a file is broken they want to be told which line is broken, not to receive a
stack trace. The command is going to be driven from a shell script, so success and
failure have to be distinguishable without reading the output, and the converted
data must not be polluted by chatter.
