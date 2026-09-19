<!-- Written by `vacant run` between attempts.
     This is machine output, not a person. It is not part of the deliverable. -->

# Acceptance feedback (attempt 1 of 3)

The checks that ship with this task were run against your
working directory. They did not all pass.

test_visible.py::check_01_split_path — assert: split_path args=('a/b/c.txt',) got={'folder': 'a/b', 'name': 'c', 'extension': 'txt'} want={'dir': 'a/b', 'name': 'c', 'ext': 'txt'} [test_visible.py:14: assert got == want, "split_path args=%r got=%r want=%r" % (args, got, want)]
test_visible.py::check_02_split_path — assert: split_path args=('readme',) got={'folder': '', 'name': 'readme', 'extension': ''} want={'dir': '', 'name': 'readme', 'ext': ''} [test_visible.py:22: assert got == want, "split_path args=%r got=%r want=%r" % (args, got, want)]

Fix the working directory. The checks run again when this process exits.
