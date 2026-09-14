# Goal

A client keeps a pile of CSV files that people edit by hand. They want to feed
that data into another tool that only speaks JSON Lines, so they need a command
that turns one CSV file into one JSON object per row.

Their files are messy in the ways hand-edited files are messy: fields containing
commas, fields containing line breaks, quotes inside quoted fields, and whole
columns left blank. When a file is broken they want to be told which line is
broken, not to receive a stack trace.
