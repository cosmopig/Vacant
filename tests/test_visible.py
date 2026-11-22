from inventory import build_summary

def test_empty():
    assert build_summary([]) == {'totals': {}, 'sku_count': 0}


def test_combines_duplicate_skus():
    rows = [{'sku': 'pen', 'quantity': 2}, {'sku': 'book', 'quantity': 3}, {'sku': 'pen', 'quantity': 5}]
    assert build_summary(rows) == {'totals': {'pen': 7, 'book': 3}, 'sku_count': 2}
