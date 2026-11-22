import csv


def totals(path='sales.csv'):
    result = {}
    with open(path, newline='') as stream:
        for row in csv.DictReader(stream):
            if row['status'].strip() == 'cancelled':
                continue
            region = row['region'].strip()
            result[region] = result.get(region, 0) + int(row['quantity']) * int(row['unit_cents'])
    return result
