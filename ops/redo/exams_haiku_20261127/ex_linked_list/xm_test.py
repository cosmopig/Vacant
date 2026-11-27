import pytest

from linked_list import LinkedList


def test_new_list_is_empty():
    assert len(LinkedList()) == 0


def test_push_adds_to_end():
    lst = LinkedList()
    lst.push(1)
    lst.push(2)
    lst.push(3)
    assert len(lst) == 3
    assert lst.pop() == 3
    assert lst.pop() == 2
    assert lst.pop() == 1


def test_unshift_adds_to_beginning():
    lst = LinkedList()
    lst.unshift(1)
    lst.unshift(2)
    assert len(lst) == 2
    assert lst.shift() == 2
    assert lst.shift() == 1


def test_shift_removes_from_beginning():
    lst = LinkedList()
    lst.push(1)
    lst.push(2)
    lst.push(3)
    assert lst.shift() == 1
    assert len(lst) == 2
    assert lst.pop() == 3


def test_pop_removes_from_end():
    lst = LinkedList()
    lst.push(1)
    lst.push(2)
    lst.push(3)
    assert lst.pop() == 3
    assert len(lst) == 2
    assert lst.shift() == 1


def test_pop_on_empty_list_raises_index_error():
    lst = LinkedList()
    with pytest.raises(IndexError) as excinfo:
        lst.pop()
    assert str(excinfo.value) != ""


def test_shift_on_empty_list_raises_index_error():
    lst = LinkedList()
    with pytest.raises(IndexError) as excinfo:
        lst.shift()
    assert str(excinfo.value) != ""


def test_pop_last_remaining_item_then_empty():
    lst = LinkedList()
    lst.push(1)
    assert lst.pop() == 1
    assert len(lst) == 0
    with pytest.raises(IndexError):
        lst.pop()


def test_delete_middle_value():
    lst = LinkedList()
    lst.push(1)
    lst.push(2)
    lst.push(3)
    lst.delete(2)
    assert len(lst) == 2
    assert lst.shift() == 1
    assert lst.pop() == 3


def test_delete_removes_only_first_occurrence():
    lst = LinkedList()
    lst.push(1)
    lst.push(2)
    lst.push(1)
    lst.push(3)
    lst.delete(1)
    assert len(lst) == 3
    assert lst.shift() == 2
    assert lst.shift() == 1
    assert lst.pop() == 3


def test_delete_head_and_tail_values():
    lst = LinkedList()
    lst.push(1)
    lst.push(2)
    lst.push(3)
    lst.delete(1)
    assert lst.shift() == 2
    lst.push(4)
    lst.delete(4)
    assert len(lst) == 1
    assert lst.pop() == 3


def test_delete_only_element_leaves_empty_list():
    lst = LinkedList()
    lst.push(5)
    lst.delete(5)
    assert len(lst) == 0
    with pytest.raises(IndexError):
        lst.shift()


def test_delete_missing_value_raises_value_error():
    lst = LinkedList()
    lst.push(1)
    lst.push(2)
    with pytest.raises(ValueError) as excinfo:
        lst.delete(99)
    assert str(excinfo.value) != ""
    assert len(lst) == 2


def test_mixed_operations_track_length():
    lst = LinkedList()
    lst.unshift(0)
    lst.push(1)
    lst.push(2)
    assert len(lst) == 3
    assert lst.shift() == 0
    assert len(lst) == 2
    assert lst.pop() == 2
    assert len(lst) == 1
    assert lst.shift() == 1
    assert len(lst) == 0
