"""已知壞樁 1：用 `str.split(",")` 拆欄位。

擋得住它的是「引號裡的逗號」與「引號裡的換行」那兩條——那正是 goal 第二段
逐字講的客戶困擾。擋不住它的驗收套件等於沒有測到題目的重點。
"""
import json
import sys


def csv_to_jsonl(text: str) -> str:
    lines = [ln for ln in text.replace("\r\n", "\n").split("\n") if ln != ""]
    if not lines:
        return ""
    header = lines[0].split(",")
    out = []
    for ln in lines[1:]:
        fields = ln.split(",")
        obj = dict(zip(header, fields))
        out.append(json.dumps(obj, ensure_ascii=False))
    return "".join(s + "\n" for s in out)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    with open(argv[0], encoding="utf-8") as f:
        sys.stdout.write(csv_to_jsonl(f.read()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
