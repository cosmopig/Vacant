import json


def build_summary(rows):
    totals = {}
    for row in rows:
        sku = row['sku']
        totals[sku] = totals.get(sku, 0) + row['quantity']
    return {'totals': totals, 'sku_count': len(totals)}


if __name__ == '__main__':
    with open('inventory.json') as stream:
        rows = json.load(stream)
    with open('out.json', 'w') as stream:
        json.dump(build_summary(rows), stream)
