"""Reference solution for ow_01_csvjson (gauge only; never enters a workspace)."""

import json
import sys


def parse_records(text):
    """Split CSV text into records, returning (records, starting_line_numbers).

    Written by hand rather than with the `csv` module on purpose: `csv` swallows
    an unclosed quote all the way to end of file, and the contract has to name
    the line the bad record starts on.
    """
    records, starts = [], []
    row, field = [], []
    in_quotes = False
    touched = False          # anything consumed for the current record yet?
    line = 1
    record_line = 1
    i, n = 0, len(text)

    while i < n:
        ch = text[i]
        if in_quotes:
            if ch == '"':
                if i + 1 < n and text[i + 1] == '"':
                    field.append('"')
                    i += 2
                    continue
                in_quotes = False
                i += 1
                continue
            if ch == "\r" and i + 1 < n and text[i + 1] == "\n":
                field.append("\n")
                line += 1
                i += 2
                continue
            if ch == "\n":
                field.append("\n")
                line += 1
                i += 1
                continue
            field.append(ch)
            i += 1
            continue

        if ch == '"' and not field:
            in_quotes = True
            touched = True
            i += 1
            continue
        if ch == ",":
            row.append("".join(field))
            field = []
            touched = True
            i += 1
            continue
        if ch in "\r\n":
            i += 2 if (ch == "\r" and i + 1 < n and text[i + 1] == "\n") else 1
            line += 1
            if touched or field or row:
                row.append("".join(field))
                records.append(row)
                starts.append(record_line)
                row, field = [], []
                touched = False
            record_line = line
            continue
        field.append(ch)
        touched = True
        i += 1

    if in_quotes:
        raise ValueError("line %d: unclosed quote" % record_line)
    if touched or field or row:
        row.append("".join(field))
        records.append(row)
        starts.append(record_line)
    return records, starts


def csv_to_jsonl(text):
    records, starts = parse_records(text)
    if not records:
        return ""
    header = records[0]
    out = []
    for record, start in zip(records[1:], starts[1:]):
        if len(record) != len(header):
            raise ValueError("line %d: expected %d fields, got %d"
                             % (start, len(header), len(record)))
        obj = {}
        for name, value in zip(header, record):
            obj[name] = value          # a repeated header name overwrites: last wins
        out.append(json.dumps(obj, ensure_ascii=False))
    return "".join(line + "\n" for line in out)


def main(argv):
    if len(argv) != 2:
        sys.stderr.write("line 1: usage: python -m solution FILE\n")
        return 2
    try:
        with open(argv[1], encoding="utf-8", newline="") as handle:
            text = handle.read()
    except OSError:
        sys.stderr.write("line 1: cannot read %s\n" % argv[1])
        return 2
    try:
        out = csv_to_jsonl(text)
    except ValueError as exc:
        sys.stderr.write("%s\n" % exc)
        return 2
    sys.stdout.write(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
