import json
import pytest
from codec import loads
from service import build, render, summarize


def ev(i, owner, status="open", seconds=0):
    return {"id": i, "owner": owner, "status": status, "seconds": seconds}


def test_duplicates_and_conflicts():
    assert summarize([ev("a", "A", "done", 3), ev("a", "A", "done", 3)]) == [{"owner": "A", "seconds": 3, "done": 1}]
    with pytest.raises(ValueError, match="event conflict"):
        summarize([ev("a", "A", "done", 3), ev("a", "A", "done", 4)])


def test_owner_normalization_and_sort():
    rows = summarize([ev("1", " Cafe\u0301 ", "open", 1), ev("2", "Café", "done", 1),
                      ev("3", "b", seconds=5), ev("4", "B", seconds=5), ev("5", "z")])
    assert rows == [{"owner": "B", "seconds": 5, "done": 0}, {"owner": "b", "seconds": 5, "done": 0},
                    {"owner": "Café", "seconds": 2, "done": 1}, {"owner": "z", "seconds": 0, "done": 0}]


@pytest.mark.parametrize("seconds", [True, -1, 1.5, "3"])
def test_bad_seconds(seconds):
    with pytest.raises(ValueError, match=r"seconds must be an integer >= 0"):
        summarize([ev("1", "A", seconds=seconds)])


def test_bad_status():
    with pytest.raises(ValueError, match="invalid status"):
        summarize([ev("1", "A", "closed")])


def test_no_aliasing():
    data = [ev("1", "A", seconds=1)]
    rows = summarize(data)
    rows[0]["seconds"] = 99
    assert data == [ev("1", "A", seconds=1)]


def test_render_escape_and_empty():
    assert render([]) == "# Work log\n\n| Owner | Seconds | Done |\n|---|---:|---:|\n"
    out = render([{"owner": "a\\b|c\r\nd\re\nf", "seconds": 1, "done": 0}])
    assert out.endswith("| a\\\\b\\|c d e f | 1 | 0 |\n")


def test_codec_formats():
    assert loads('[{"id":"1","owner":"A"}]') == [{"id": "1", "owner": "A", "status": "open", "seconds": 0}]
    raw = '{"id":"1","owner":"A\u2028B\u0085"}\r\n\n{"id":"2","owner":"C"}\n'
    rows = loads(raw)
    assert [r["owner"] for r in rows] == ["A\u2028B\u0085", "C"]


def test_build_atomic_and_repeatable(tmp_path):
    src, out = tmp_path / "e.jsonl", tmp_path / "R.md"
    src.write_text(json.dumps(ev("1", "A", "done", 2)) + "\n", encoding="utf-8")
    assert build(src, out) == [{"owner": "A", "seconds": 2, "done": 1}]
    first = out.read_bytes()
    build(src, out)
    assert out.read_bytes() == first
    src.write_text(json.dumps(ev("1", "A", "bad")) + "\n", encoding="utf-8")
    with pytest.raises(ValueError):
        build(src, out)
    assert out.read_bytes() == first
    assert sorted(p.name for p in tmp_path.iterdir()) == ["R.md", "e.jsonl"]
