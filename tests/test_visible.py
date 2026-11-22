from counts import merge_counts

def test_empty():
    assert merge_counts() == {}
