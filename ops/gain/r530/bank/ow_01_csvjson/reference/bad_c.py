"""Known-bad C: the skeleton. Every name exists, almost nothing happens."""
import json
import sys


def csv_to_jsonl(text):
    lines = text.splitlines()
    if len(lines) < 2:
        return ""
    header = lines[0].split(",")
    return json.dumps(dict.fromkeys(header, "")) + "\n"


def main(argv):
    sys.stdout.write(csv_to_jsonl(open(argv[1], encoding="utf-8").read()))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
