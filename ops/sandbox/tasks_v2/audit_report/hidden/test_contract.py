import copy
import json
from pathlib import Path
import pytest
from service import summarize, render, build
from codec import loads

def test_audit_delivered_bytes_and_idempotent_build(tmp_path):
    # SPEC §2
    # SPEC §3
    # SPEC §4
    rows = summarize(loads(Path("events.jsonl").read_text()))
    expected = render(rows).encode("utf-8")
    assert Path("REPORT.md").read_bytes() == expected
    assert build("events.jsonl", tmp_path/"report.md") == rows
    build("events.jsonl", tmp_path/"report.md")
    assert (tmp_path/"report.md").read_bytes() == expected

def test_audit_dedup_unicode_ties_escaping_and_legacy():
    # SPEC §1
    # SPEC §2
    # SPEC §4
    rows = [{"id":"a","owner":" Cafe\u0301 ","status":"done","seconds":2},
            {"id":"b","owner":"café","seconds":2},
            {"id":"c","owner":"z"+chr(92)+"|x\ny","seconds":0}]
    original = copy.deepcopy(rows)
    result = summarize(loads(json.dumps(rows+[rows[0]])))
    assert [r["owner"] for r in result] == ["Café","café","z"+chr(92)+"|x\ny"]
    assert result[0]["seconds"] == 2 and result[1]["done"] == 0
    assert chr(92)*3+"|x y" in render(result)
    assert rows == original
    assert render(summarize([])) == "# Work log\n\n| Owner | Seconds | Done |\n|---|---:|---:|\n"

def test_audit_conflict_and_atomic_errors(tmp_path):
    # SPEC §1
    # SPEC §3
    row = {"id":"a","owner":"A","seconds":1}
    with pytest.raises(ValueError, match="^event conflict$"):
        summarize([row, {**row,"seconds":2}])
    target = tmp_path/"report.md"
    target.write_text("keep")
    for change, message in [({"status":"bad"},"invalid status"), ({"seconds":True},"seconds must be an integer >= 0")]:
        source = tmp_path/"events.jsonl"
        source.write_text(json.dumps({**row,**change}))
        with pytest.raises(ValueError, match="^"+message+"$"):
            build(source, target)
            assert target.read_text() == "keep"

def test_audit_jsonl_preserves_unicode_line_separators():
    # SPEC §1
    # SPEC §4
    for separator in ("\u2028", "\u0085"):
        name = "a"+separator+"b"
        rows = [{"id":"a", "owner":name, "seconds":1, "status":"done"},
                {"id":"b", "owner":name, "seconds":2}]
        raw = "\r\n\r\n".join(json.dumps(row, ensure_ascii=False) for row in rows)+"\r\n"
        assert loads(raw) == rows
        assert summarize(loads(raw)) == [{"owner":name, "seconds":3, "done":1}]
