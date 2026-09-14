# anchor_kind: contract
# anchor: `dumps` writes the top-level names first in name order, then each heading
# in name order with its own names in name order
# derivation: whatever order the dictionary was built in, the written form is in
# name order with the plain names above the headings.


def run(solution):
    data = {"zebra": 1, "apple": 2, "mango": {"b": 1, "a": 2}, "banana": {"x": 1}}
    written = solution.dumps(data)
    lines = [line for line in written.splitlines() if line]
    want = ["apple = 2", "zebra = 1", "[banana]", "x = 1", "[mango]", "a = 2", "b = 1"]
    assert lines == want, "args=%r got=%r want=%r" % (data, lines, want)
