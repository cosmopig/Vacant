import csv
import io


def export_csv(rows, fields):
    buf = io.StringIO()
    writer = csv.DictWriter(
        buf, fieldnames=list(fields), restval='', extrasaction='ignore',
        lineterminator='\n',
    )
    writer.writeheader()
    for row in rows:
        writer.writerow({f: ('' if row.get(f) is None else row.get(f)) for f in fields})
    return buf.getvalue()
