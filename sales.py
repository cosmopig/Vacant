import csv


def totals(path='sales.csv'):
    result = {}
    with open(path, newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            if (row.get('status') or '').strip().lower() == 'cancelled':
                continue
            region = (row.get('region') or '').strip()
            cents = int(row['quantity'].strip()) * int(row['unit_cents'].strip())
            result[region] = result.get(region, 0) + cents
    return result
