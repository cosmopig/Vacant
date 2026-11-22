from service import summarize

def test_one_event():
    assert summarize([{"id":"1","owner":"A","status":"done","seconds":2}]) == [{"owner":"A","seconds":2,"done":1}]
