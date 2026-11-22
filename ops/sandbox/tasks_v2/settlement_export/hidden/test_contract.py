import copy
import csv
import io
import json
from pathlib import Path
import pytest
from service import summarize, build, render
from codec import loads

def test_settlement_delivered_exact_file_and_repeat(tmp_path):
    # SPEC §2
    # SPEC §4
    rows = summarize(loads(Path("transactions.json").read_text()))
    expected = render(rows).encode("utf-8")
    assert Path("settlement.csv").read_bytes() == expected
    assert b"\r" not in expected and not expected.startswith(b"\xef\xbb\xbf")
    assert build("transactions.json", tmp_path/"out.csv") == rows
    build("transactions.json", tmp_path/"out.csv")
    assert (tmp_path/"out.csv").read_bytes() == expected

def test_settlement_rounding_order_legacy_and_empty():
    # SPEC §1
    # SPEC §4
    rows = [{"merchant":" Z ","currency":"usd","amount":"0.005"},
            {"merchant":"z","currency":"USD","amount":"0.015","kind":"refund"},
            {"status":"canceled"}]
    before = copy.deepcopy(rows)
    assert summarize(rows) == [{"merchant":"z","currency":"USD","total":"-0.02","count":2}]
    assert rows == before
    assert loads(json.dumps(rows[0])+"\n\n"+json.dumps(rows[1])) == rows[:2]
    assert render(summarize([])) == "merchant,currency,total,count\n"

def test_settlement_validation_keeps_existing_output(tmp_path):
    # SPEC §3
    output = tmp_path/"out.csv"
    output.write_text("keep")
    for change, message in [({"currency":"GBP"},"invalid currency"), ({"amount":"NaN"},"invalid amount"), ({"kind":"adjust"},"invalid kind"), ({"status":"bad"},"invalid status")]:
        row = {"merchant":"a","currency":"USD","amount":"2",**change}
        source = tmp_path/"in.json"
        source.write_text(json.dumps([row]))
        with pytest.raises(ValueError, match="^"+message+"$"):
            build(source, output)
        assert output.read_text() == "keep"

def test_settlement_csv_quotes_embedded_carriage_returns():
    # SPEC §2
    name = "a\rb\r\nc\nd"
    rows = [{"merchant":name, "currency":"USD", "total":"2.00", "count":1}]
    encoded = render(rows)
    assert list(csv.reader(io.StringIO(encoded, newline=""))) == [
        ["merchant", "currency", "total", "count"], [name, "USD", "2.00", "1"]]
    assert encoded.endswith("\n") and not encoded.endswith("\r\n")
