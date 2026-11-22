import pytest
from pages import page

def test_edges():
    assert page([1, 2, 3], 2, 2) == [3]
    assert page([], 1, 2) == []
    assert page([1], 4, 2) == []
    for number, size in ((0, 2), (1, 0), (-1, 2)):
        with pytest.raises(ValueError):
            page([1], number, size)
