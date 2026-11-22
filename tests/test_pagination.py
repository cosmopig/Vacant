import pytest

from pages import page


def test_later_pages():
    items = [1, 2, 3, 4, 5]
    assert page(items, 2, 2) == [3, 4]
    assert page(items, 3, 2) == [5]
    assert page(items, 4, 2) == []


def test_empty_items():
    assert page([], 1, 1) == []


@pytest.mark.parametrize("number,size", [(0, 2), (-1, 2), (1, 0), (1, -1)])
def test_invalid_parameters(number, size):
    with pytest.raises(ValueError):
        page([], number, size)
