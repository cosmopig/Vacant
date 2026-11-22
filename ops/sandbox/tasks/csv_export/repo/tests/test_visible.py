import csv
import io
from export import export_csv

def test_header():
    assert list(csv.reader(io.StringIO(export_csv([], ['name'])))) == [['name']]
