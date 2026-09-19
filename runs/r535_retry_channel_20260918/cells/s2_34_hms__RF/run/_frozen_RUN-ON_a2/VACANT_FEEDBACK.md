<!-- Written by `vacant run` between attempts.
     This is machine output, not a person. It is not part of the deliverable. -->

# Acceptance feedback (attempt 1 of 3)

The checks that ship with this task were run against your
working directory. They did not all pass.

test_visible.py::check_01_hms — assert: hms args=(59,) got='0:00:59' want='00:59' [test_visible.py:14: assert got == want, "hms args=%r got=%r want=%r" % (args, got, want)]
test_visible.py::check_03_hms — assert: hms args=(-1,) got='0:00:01' want=ValueError to be raised [test_visible.py:35: raise AssertionError("hms args=%r got=%r want=ValueError to be raised" %]

Fix the working directory. The checks run again when this process exits.
