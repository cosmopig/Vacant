import csv
import io

from export import export_csv


def parse(text):
    return list(csv.reader(io.StringIO(text, newline='')))


def test_empty_rows_has_header():
    assert parse(export_csv([], ['a', 'b'])) == [['a', 'b']]


def test_field_order_follows_fields():
    out = export_csv([{'b': 2, 'a': 1}], ['a', 'b'])
    assert parse(out) == [['a', 'b'], ['1', '2']]


def test_missing_and_none_are_blank():
    out = export_csv([{'a': 1}, {'a': None, 'b': 'x'}], ['a', 'b'])
    assert parse(out) == [['a', 'b'], ['1', ''], ['', 'x']]


def test_extra_keys_ignored():
    assert parse(export_csv([{'a': 1, 'z': 9}], ['a'])) == [['a'], ['1']]


def test_special_characters_round_trip():
    values = ['a,b', 'say "hi"', 'line1\nline2', 'cr\r\nlf', '  spaced  ', '']
    fields = [f'f{i}' for i in range(len(values))]
    row = dict(zip(fields, values))
    assert parse(export_csv([row], fields)) == [fields, values]


def test_special_characters_in_header():
    fields = ['x,y', 'q"t']
    assert parse(export_csv([{'x,y': 1, 'q"t': 2}], fields)) == [fields, ['1', '2']]


def test_round_trip_via_dictreader():
    rows = [{'name': 'Ann, Jr.', 'note': 'he said "ok"\nbye'}, {'name': 'Bob'}]
    out = export_csv(rows, ['name', 'note'])
    back = list(csv.DictReader(io.StringIO(out, newline='')))
    assert back == [{'name': 'Ann, Jr.', 'note': 'he said "ok"\nbye'},
                    {'name': 'Bob', 'note': ''}]
