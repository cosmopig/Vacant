"""Settlement computation and atomic CSV delivery."""
import csv
import io
import os
from pathlib import Path
import tempfile
import unicodedata
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN
from checks import objects


CURRENCIES = {"USD", "EUR"}
KINDS = {"sale", "refund"}
STATUSES = {"posted", "canceled"}
CENT = Decimal("0.01")


def _merchant(value):
    if not isinstance(value, str):
        raise ValueError("invalid merchant")
    return unicodedata.normalize("NFC", value).strip().casefold()


def _currency(value):
    if not isinstance(value, str) or value.strip().upper() not in CURRENCIES:
        raise ValueError("invalid currency")
    return value.strip().upper()


def _amount(value):
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise ValueError("invalid amount")
    try:
        result = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        raise ValueError("invalid amount") from None
    if not result.is_finite() or result < 0:
        raise ValueError("invalid amount")
    return result.quantize(CENT, rounding=ROUND_HALF_EVEN)


def summarize(rows):
    totals = {}
    for row in objects(rows):
        status = row.get("status", "posted")
        if status not in STATUSES:
            raise ValueError("invalid status")
        if status == "canceled":
            continue
        currency = _currency(row.get("currency"))
        kind = row.get("kind", "sale")
        if kind not in KINDS:
            raise ValueError("invalid kind")
        amount = _amount(row.get("amount"))
        key = (_merchant(row.get("merchant")), currency)
        value, count = totals.get(key, (Decimal(0), 0))
        totals[key] = (value + amount if kind == "sale" else value - amount, count + 1)
    return [dict(merchant=m, currency=c, total=format(value + Decimal("0.00"), ".2f"), count=count)
            for (m, c), (value, count) in sorted(totals.items())]


def _csv_line(fields):
    out = io.StringIO(newline="")
    csv.writer(out, lineterminator="\n", quoting=csv.QUOTE_MINIMAL).writerow(fields)
    return out.getvalue()


def render(rows):
    header = _csv_line(["merchant", "currency", "total", "count"])
    return header + "".join(_csv_line((r["merchant"], r["currency"], r["total"], r["count"]))
                            for r in rows)


def build(input_path="transactions.json", output_path="settlement.csv"):
    from codec import load
    rows = summarize(load(input_path))
    output = Path(output_path)
    data = render(rows).encode("utf-8")
    fd, temp = tempfile.mkstemp(dir=output.parent, prefix=".settlement-", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        umask = os.umask(0)
        os.umask(umask)
        os.chmod(temp, 0o666 & ~umask)
        os.replace(temp, output)
    except BaseException:
        try:
            os.unlink(temp)
        except FileNotFoundError:
            pass
        raise
    return rows


if __name__ == "__main__":
    build()
