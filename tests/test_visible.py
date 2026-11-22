from pages import page

def test_first():
    assert page([1, 2, 3], 1, 2) == [1, 2]
