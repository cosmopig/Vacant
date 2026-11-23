import json
from pathlib import Path
from inventory import build_summary

def test_summary():
    assert build_summary([{'sku': 'x', 'quantity': 2}, {'sku': 'x', 'quantity': -2}]) == {'totals': {'x': 0}, 'sku_count': 1}
    assert json.loads(Path('out.json').read_text()) == {'totals': {'pen': 7, 'book': 3}, 'sku_count': 2}
