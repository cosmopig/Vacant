from sales import totals

def test_empty(tmp_path):
    path = tmp_path / 'empty.csv'
    path.write_text('region,quantity,unit_cents,status\n')
    assert totals(path) == {}
