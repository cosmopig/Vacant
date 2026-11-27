"""Acceptance tests for the doubly linked list exercise (route of train stations)."""

import pytest

from linked_list import Node, LinkedList


def test_node_stores_its_value():
    """REQ: "Your `Node` class should keep track of its value, as well as which nodes precede or follow." """
    node = Node(4)
    assert 4 in vars(node).values()
    # The stub signature accepts optional neighbour arguments.
    Node(4, None, None)


def test_new_list_is_empty_with_length_zero():
    """REQ: "The size of a route is measured not by how far the train travels, but by how many stations it stops at." """
    assert len(LinkedList()) == 0


def test_len_counts_stations_not_station_numbers():
    """REQ: "The size of a route is measured not by how far the train travels, but by how many stations it stops at." """
    ll = LinkedList()
    ll.push(1000)
    ll.push(2)
    ll.push(999)
    assert len(ll) == 3


def test_station_is_a_number_stored_intact():
    """REQ: "Each station will simply be represented by a number." """
    ll = LinkedList()
    ll.push(0)
    ll.push(-5)
    ll.push(123456)
    assert ll.pop() == 123456
    assert ll.pop() == -5
    assert ll.pop() == 0


def test_push_adds_station_to_end():
    """REQ: "Routes can be extended, adding stations to the beginning or end of a route." """
    ll = LinkedList()
    ll.push(1)
    ll.push(2)
    ll.push(3)
    assert len(ll) == 3
    assert ll.pop() == 3
    assert ll.pop() == 2
    assert ll.pop() == 1


def test_unshift_adds_station_to_beginning():
    """REQ: "Routes can be extended, adding stations to the beginning or end of a route." """
    ll = LinkedList()
    ll.unshift(2)
    ll.unshift(1)
    ll.push(3)
    assert len(ll) == 3
    assert ll.shift() == 1
    assert ll.shift() == 2
    assert ll.pop() == 3


def test_pop_removes_and_returns_last_station():
    """REQ: "They can also be shortened by removing stations from the beginning or the end of a route." """
    ll = LinkedList()
    ll.push(1)
    ll.push(2)
    ll.push(3)
    assert ll.pop() == 3
    assert len(ll) == 2
    assert ll.pop() == 2
    assert len(ll) == 1


def test_shift_removes_and_returns_first_station():
    """REQ: "They can also be shortened by removing stations from the beginning or the end of a route." """
    ll = LinkedList()
    ll.push(1)
    ll.push(2)
    ll.push(3)
    assert ll.shift() == 1
    assert len(ll) == 2
    assert ll.shift() == 2
    assert len(ll) == 1


def test_pop_on_empty_list_raises_index_error():
    """REQ: "Additionally, an `IndexError` should be thrown if there are no nodes left to `pop()`." """
    ll = LinkedList()
    with pytest.raises(IndexError):
        ll.pop()


def test_shift_on_empty_list_raises_index_error():
    """REQ: "Unlike the core exercise, we will be testing error conditions by calling `pop` and `shift` on empty `LinkedLists`, so you will need to `raise` errors appropriately." """
    ll = LinkedList()
    with pytest.raises(IndexError):
        ll.shift()


def test_pop_after_last_station_removed_raises_index_error():
    """REQ: "Additionally, an `IndexError` should be thrown if there are no nodes left to `pop()`." """
    ll = LinkedList()
    ll.push(1)
    assert ll.pop() == 1
    with pytest.raises(IndexError):
        ll.pop()


def test_error_messages_are_meaningful():
    """REQ: "When you do this, you should always include a **meaningful error message** to indicate what the source of the error is." """
    ll = LinkedList()
    with pytest.raises(IndexError) as pop_info:
        ll.pop()
    assert str(pop_info.value).strip() != ""

    with pytest.raises(IndexError) as shift_info:
        ll.shift()
    assert str(shift_info.value).strip() != ""

    with pytest.raises(ValueError) as delete_info:
        ll.delete(9)
    assert str(delete_info.value).strip() != ""


def test_delete_middle_station_keeps_order_of_others():
    """REQ: "Sometimes a station gets closed down, and in that case the station needs to be removed from the route, even if it is not at the beginning or end of the route." """
    ll = LinkedList()
    ll.push(1)
    ll.push(2)
    ll.push(3)
    ll.push(4)
    ll.delete(2)
    assert len(ll) == 3
    assert ll.pop() == 4
    assert ll.pop() == 3
    assert ll.shift() == 1


def test_delete_first_and_last_station():
    """REQ: "Sometimes a station gets closed down, and in that case the station needs to be removed from the route, even if it is not at the beginning or end of the route." """
    ll = LinkedList()
    ll.push(1)
    ll.push(2)
    ll.push(3)
    ll.delete(1)
    assert len(ll) == 2
    ll.delete(3)
    assert len(ll) == 1
    assert ll.pop() == 2
    assert len(ll) == 0


def test_delete_decreases_length_each_time():
    """REQ: "`delete` will take one argument, which is the value to be removed from the linked list." """
    ll = LinkedList()
    ll.push(1)
    ll.push(2)
    ll.push(3)
    ll.delete(2)
    assert len(ll) == 2
    ll.delete(1)
    assert len(ll) == 1


def test_delete_removes_only_first_occurrence():
    """REQ: "If the value appears more than once, only the **first** occurrence should be removed." """
    ll = LinkedList()
    ll.push(5)
    ll.push(1)
    ll.push(5)
    ll.push(2)
    ll.delete(5)
    assert len(ll) == 3
    assert ll.shift() == 1
    assert ll.shift() == 5
    assert ll.shift() == 2


def test_delete_missing_value_raises_value_error():
    """REQ: "This particular exercise requires that you use the [raise statement][raise] to "throw" a `ValueError` when a node value being `delete()`-ed is not found in the linked list." """
    ll = LinkedList()
    ll.push(1)
    ll.push(2)
    with pytest.raises(ValueError):
        ll.delete(9)


def test_delete_on_empty_list_raises_value_error():
    """REQ: "This particular exercise requires that you use the [raise statement][raise] to "throw" a `ValueError` when a node value being `delete()`-ed is not found in the linked list." """
    ll = LinkedList()
    with pytest.raises(ValueError):
        ll.delete(1)


def test_deleting_only_station_leaves_empty_route():
    """REQ: "Sometimes a station gets closed down, and in that case the station needs to be removed from the route, even if it is not at the beginning or end of the route." """
    ll = LinkedList()
    ll.push(7)
    ll.delete(7)
    assert len(ll) == 0
    with pytest.raises(IndexError):
        ll.pop()


def test_len_tracks_mixed_operations():
    """REQ: "Routes can be extended, adding stations to the beginning or end of a route." """
    ll = LinkedList()
    ll.push(1)
    ll.unshift(0)
    ll.push(2)
    assert len(ll) == 3
    assert ll.shift() == 0
    assert len(ll) == 2
    assert ll.pop() == 2
    assert len(ll) == 1
