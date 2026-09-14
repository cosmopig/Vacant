# Goal

A client has a text log written by their own service and wants to know, per
endpoint, how many requests there were, what share of them failed, and how slow
the slow ones are. The log is machine-written but not clean: some lines are
truncated or garbled, and those must not stop the run.

Failed means the server's own fault, the five-hundreds; a client sending a bad
request is not a failure of theirs. Their idea of slow is the ordinary middle and
the unlucky tail.

They want the busiest endpoints at the top, and when two are equally busy they
want the order to be the same every time they run it.

They also want to know how many lines were unusable, because a sudden jump in that
number is their signal that something upstream changed. Blank lines are just noise
from the rotation script and should not count as anything at all.

Finally they want to eyeball a file from the shell without writing a script.
