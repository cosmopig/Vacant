import pytest

from linked_list import LinkedList


def build(*items):
    """Create a LinkedList by pushing the given items onto the end, in order."""
    ll = LinkedList()
    for item in items:
        ll.push(item)
    return ll


def values(ll):
    """Return the station numbers of a LinkedList, in route order."""
    return list(ll)


def test_empty_list_has_length_zero():
    ll = LinkedList()
    # SRC: "The size of a route is measured not by how far the train travels, but by how many stations it stops at."
    assert len(ll) == 0


def test_push_adds_stations_to_end_of_route():
    ll = build(1, 2, 3)
    # SRC: "Each station along the train's route will be represented by a node in the linked list."
    assert len(ll) == 3
    # SRC: "Routes can be extended, adding stations to the beginning or end of a route."
    assert values(ll) == [1, 2, 3]


def test_unshift_adds_station_to_beginning_of_route():
    ll = build(1, 2, 3)
    ll.unshift(0)
    # SRC: "Routes can be extended, adding stations to the beginning or end of a route."
    assert values(ll) == [0, 1, 2, 3]
    # SRC: "The size of a route is measured not by how far the train travels, but by how many stations it stops at."
    assert len(ll) == 4


def test_pop_removes_station_from_end_of_route():
    ll = build(0, 1, 2, 3)
    ll.pop()
    # SRC: "They can also be shortened by removing stations from the beginning or the end of a route."
    assert values(ll) == [0, 1, 2]


def test_shift_removes_station_from_beginning_of_route():
    ll = build(0, 1, 2)
    ll.shift()
    # SRC: "They can also be shortened by removing stations from the beginning or the end of a route."
    assert values(ll) == [1, 2]


def test_delete_removes_station_in_the_middle():
    ll = build(1, 2, 3)
    ll.delete(2)
    # SRC: "Sometimes a station gets closed down, and in that case the station needs to be removed from the route, even if it is not at the beginning or end of the route."
    assert values(ll) == [1, 3]


def test_delete_removes_station_at_beginning():
    ll = build(1, 2, 3)
    ll.delete(1)
    # SRC: "`delete` will take one argument, which is the value to be removed from the linked list."
    assert values(ll) == [2, 3]


def test_delete_removes_station_at_end():
    ll = build(1, 2, 3)
    ll.delete(3)
    # SRC: "Sometimes a station gets closed down, and in that case the station needs to be removed from the route, even if it is not at the beginning or end of the route."
    assert values(ll) == [1, 2]


def test_delete_removes_only_first_occurrence():
    ll = build(1, 2, 1, 3)
    ll.delete(1)
    # SRC: "If the value appears more than once, only the **first** occurrence should be removed."
    assert values(ll) == [2, 1, 3]


def test_length_decreases_after_delete():
    ll = build(1, 2, 3)
    ll.delete(2)
    # SRC: "The size of a route is measured not by how far the train travels, but by how many stations it stops at."
    assert len(ll) == 2


def test_delete_missing_value_raises_value_error():
    ll = build(1, 2)
    # SRC: "`ValueError` when a node value being `delete()`-ed is not found in the linked list."
    with pytest.raises(ValueError):
        ll.delete(9)


def test_pop_on_empty_list_raises_index_error():
    ll = LinkedList()
    # SRC: "Additionally, an `IndexError` should be thrown if there are no nodes left to `pop()`."
    with pytest.raises(IndexError):
        ll.pop()


def test_shift_on_empty_list_raises_error():
    ll = LinkedList()
    # SRC: "Unlike the core exercise, we will be testing error conditions by calling `pop` and `shift` on empty `LinkedLists`, so you will need to `raise` errors appropriately."
    with pytest.raises(Exception):
        ll.shift()
