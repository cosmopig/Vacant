"""Settlement computation and atomic CSV delivery."""
import csv
import io
import os
from pathlib import Path
import tempfile
import unicodedata
from decimal import Decimal, ROUND_HALF_EVEN
from checks import objects, number, text


def summarize(rows):
    totals = {}
    for row in objects(rows):
        if row.get("status") == "canceled":
            continue
        key = (row["merchant"], row["currency"])
        value, count = totals.get(key, (Decimal(0), 0))
        amount = number(row["amount"], "amount")
        totals[key] = (value + amount, count+1)
    return [dict(merchant=m, currency=c, total=format(value, ".2f"), count=count)
            for (m,c), (value,count) in sorted(totals.items())]


def render(rows):
    out = io.StringIO(newline="")
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(["merchant", "currency", "total", "count"])
    writer.writerows((r["merchant"], r["currency"], r["total"], r["count"]) for r in rows)
    return out.getvalue()


def build(input_path="transactions.json", output_path="settlement.csv"):
    from codec import load
    rows = summarize(load(input_path))
    output = Path(output_path)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="", dir=output.parent, delete=False) as stream:
        temp = stream.name
        stream.write(render(rows))
    os.replace(temp, output)
    return rows


if __name__ == "__main__":
    build()
