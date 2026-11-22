from pathlib import Path

from sales import totals

HERE = Path(__file__).resolve().parent.parent


def test_sample_file():
    assert totals(HERE / 'sales.csv') == {'North': 725, 'South, Coast': 300}


def test_trim_combine_and_cancelled(tmp_path):
    path = tmp_path / 's.csv'
    path.write_text(
        'region,quantity,unit_cents,status\n'
        '  East ,2,10,paid\n'
        'East,3,5,paid\n'
        'East,100,100,cancelled\n'
        '" West ",1,7,paid\n'
    )
    assert totals(path) == {'East': 35, 'West': 7}


def test_only_cancelled(tmp_path):
    path = tmp_path / 's.csv'
    path.write_text('region,quantity,unit_cents,status\nNorth,1,1,cancelled\n')
    assert totals(path) == {}
