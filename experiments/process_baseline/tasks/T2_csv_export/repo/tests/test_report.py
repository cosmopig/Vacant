from report import summarize, render_text

def test_summarize():
    assert summarize([{"name":"a","hours":1},{"name":"a","hours":2}]) == {"a": 3}

def test_render():
    assert render_text({"b": 1, "a": 2}) == "a: 2.0h\nb: 1.0h"
