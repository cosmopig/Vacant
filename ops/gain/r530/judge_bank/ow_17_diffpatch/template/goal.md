# Goal

A client reviews changes to plain text files by hand. They want to see what changed
between two versions as a list of pieces, and they want to be able to take that
list and put it back onto the old version to get the new one.

They want the difference described as separate pieces, one per place that changed,
so that a reviewer sees the two lines that moved rather than one block covering
everything between them. A piece must not carry lines that did not change: not at
its start, not at its end. A file that did not change at all produces no pieces.

Applying a list of pieces to a version they do not fit is the dangerous case --
someone edited the file in between -- and has to be refused loudly rather than
producing a mangled file. The same goes for a list of pieces that is out of order,
that overlaps itself, or that is simply malformed.

Applying must not touch what it was given, because they keep the old version
around. Files with many identical lines are common in their data, and going out and
back has to survive them.
