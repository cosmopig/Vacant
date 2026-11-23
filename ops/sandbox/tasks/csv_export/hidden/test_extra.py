import csv
import io
from export import export_csv

def test_rows():
    rows = [{'name': 'A, "B"\nC', 'age': 3}, {'age': 4}]
    parsed = list(csv.reader(io.StringIO(export_csv(rows, ['age', 'name']))))
    assert parsed == [['age', 'name'], ['3', 'A, "B"\nC'], ['4', '']]
