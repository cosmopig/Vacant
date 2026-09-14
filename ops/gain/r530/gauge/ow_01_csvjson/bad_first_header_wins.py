"""已知壞樁 3：標頭重名時「第一個為準」（契約寫的是**最後一個**），
空欄變成 `None` 而不是 `""`，錯誤訊息沒有行號。

它是三個樁裡**最接近正確**的一個——只有少數幾條隱藏驗收抓得到它。
留著它的理由：只擋得住「明顯亂寫」的驗收套件，量不出 R530 想量的差
（`vacant/suitegauge.py` 的判準：每個已知壞樁都要被擋，不是只擋得住最爛的那個）。
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
        if len(fields) != len(header):
            raise ValueError("bad row")          # 沒有行號
        obj = {}
        for key, value in zip(header, fields):
            if key not in obj:                   # 第一個為準（契約說最後一個）
                obj[key] = value if value != "" else None
        out.append(json.dumps(obj, ensure_ascii=False))
    return "".join(s + "\n" for s in out)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    with open(argv[0], encoding="utf-8") as f:
        sys.stdout.write(csv_to_jsonl(f.read()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
