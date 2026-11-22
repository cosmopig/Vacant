import json


def build_summary(rows):
    return {'totals': {}, 'sku_count': 0}


if __name__ == '__main__':
    with open('inventory.json') as stream:
        rows = json.load(stream)
    with open('out.json', 'w') as stream:
        json.dump(build_summary(rows), stream)
