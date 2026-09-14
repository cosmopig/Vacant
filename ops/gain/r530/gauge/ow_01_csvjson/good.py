"""ow_01_csvjson 的參考解——量具的正向那一半（`PR-3`／E-3）。

它**必須全過**可見與隱藏。不全過的意思不是「參考解寫得不好」，
是**題目的驗收與契約對不起來**——那要改題目，不是改這一份。
（`vacant/suitegauge.py` 的單邊保證：擋得住已知壞解 ≠ 涵蓋真需求。
  這一份管的是另一邊：**真需求至少有一個解到得了**。）
"""
import json
import sys


def _records(text):
    """把 CSV 文字切成 `[(fields, start_line), …]`。未閉合引號丟 ValueError。"""
    records = []
    field_chars = []
    row = []
    i, n = 0, len(text)
    line = 1
    row_start = 1
    in_quotes = False
    saw_any = False
    while i < n:
        ch = text[i]
        if in_quotes:
            if ch == '"':
                if i + 1 < n and text[i + 1] == '"':
                    field_chars.append('"')
                    i += 2
                    continue
                in_quotes = False
                i += 1
                continue
            if ch == "\n":
                line += 1
            field_chars.append(ch)
            i += 1
            continue
        if ch == '"':
            in_quotes = True
            saw_any = True
            i += 1
            continue
        if ch == ",":
            row.append("".join(field_chars))
            field_chars = []
            saw_any = True
            i += 1
            continue
        if ch in "\r\n":
            if ch == "\r" and i + 1 < n and text[i + 1] == "\n":
                i += 2
            else:
                i += 1
            row.append("".join(field_chars))
            field_chars = []
            records.append((row, row_start))
            row = []
            saw_any = False
            line += 1
            row_start = line
            continue
        field_chars.append(ch)
        saw_any = True
        i += 1
    if in_quotes:
        raise ValueError(f"line {row_start}: quoted field is never closed")
    if field_chars or row or saw_any:
        row.append("".join(field_chars))
        records.append((row, row_start))
    return records


def csv_to_jsonl(text: str) -> str:
    records = _records(text)
    if not records:
        return ""
    header = records[0][0]
    out = []
    for fields, start_line in records[1:]:
        if len(fields) != len(header):
            raise ValueError(
                f"line {start_line}: expected {len(header)} fields, "
                f"found {len(fields)}")
        obj = {}
        for key, value in zip(header, fields):
            obj[key] = value           # 重名 ⇒ 後面的蓋掉前面的 ⇒ 最後一個為準
        out.append(json.dumps(obj, ensure_ascii=False))
    return "".join(line + "\n" for line in out)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        sys.stderr.write("line 0: usage: python3 -m solution FILE\n")
        return 2
    try:
        with open(argv[0], encoding="utf-8") as f:
            text = f.read()
    except OSError as exc:
        sys.stderr.write(f"line 0: {exc.strerror or 'cannot read file'}\n")
        return 2
    try:
        out = csv_to_jsonl(text)
    except ValueError as exc:
        sys.stderr.write(str(exc) + "\n")
        return 2
    sys.stdout.write(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
