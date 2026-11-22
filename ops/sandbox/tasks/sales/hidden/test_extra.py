from sales import totals

def test_data(tmp_path):
    assert totals() == {'North': 725, 'South, Coast': 300}
    path = tmp_path / 'extra.csv'
    path.write_text('region,quantity,unit_cents,status\n East ,2,75,paid\nEast,-1,75,paid\nWest,9,10,cancelled\n')
    assert totals(path) == {'East': 75}
