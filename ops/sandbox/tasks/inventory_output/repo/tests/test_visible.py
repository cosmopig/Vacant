from inventory import build_summary

def test_empty():
    assert build_summary([]) == {'totals': {}, 'sku_count': 0}
