"""已知壞樁 2：欄數不符時爆 traceback 而不是 `line <N>: <reason>`。

擋得住它的是行號那兩條。goal 的最後一句逐字是
「they want to be told which line is broken, not to receive a stack trace」
——這個樁做的正是客戶明說不要的那件事。
"""
import csv
import io
import json
import sys


def csv_to_jsonl(text: str) -> str:
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        return ""
    header = rows[0]
    out = []
    for fields in rows[1:]:
        # 欄數不符直接爆 IndexError——不是契約要的 ValueError("line N: …")
        obj = {header[i]: fields[i] for i in range(len(header))}
        out.append(json.dumps(obj, ensure_ascii=False))
    return "".join(s + "\n" for s in out)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    with open(argv[0], encoding="utf-8") as f:
        sys.stdout.write(csv_to_jsonl(f.read()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
