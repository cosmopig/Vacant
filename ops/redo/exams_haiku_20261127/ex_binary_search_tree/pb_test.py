"""Acceptance tests for the binary search tree exercise.

Each check function covers one property taken from the requirements text.
"""

from binary_search_tree import BinarySearchTree


def _values(node):
    """Return every data value in the subtree rooted at node, in-order."""
    if node is None:
        return []
    return _values(node.left) + [node.data] + _values(node.right)


def _assert_is_search_tree(node):
    """Assert the ordering rule holds at every node of the subtree."""
    if node is None:
        return
    left_values = _values(node.left)
    right_values = _values(node.right)
    assert all(v <= node.data for v in left_values), (
        f"left subtree of {node.data} contains a larger value: {left_values}"
    )
    assert all(v > node.data for v in right_values), (
        f"right subtree of {node.data} contains a value not greater: {right_values}"
    )
    _assert_is_search_tree(node.left)
    _assert_is_search_tree(node.right)


def test_single_value_tree_root_holds_value_and_nil_children():
    """REQ: "Each node contains a piece of data (e.g. the number 3), a variable named `left`, and a variable named `right`."

    Property: a tree built from one number has a root node holding that number,
    and its left and right variables point at nil.
    """
    root = BinarySearchTree([3]).data()
    assert root.data == 3
    assert root.left is None
    assert root.right is None


def test_node_exposes_data_left_and_right_attributes():
    """REQ: "Each node contains a piece of data (e.g. the number 3), a variable named `left`, and a variable named `right`."

    Property: the root node exposes the attributes named data, left and right.
    """
    root = BinarySearchTree([3]).data()
    assert hasattr(root, "data")
    assert hasattr(root, "left")
    assert hasattr(root, "right")


def test_first_value_becomes_root():
    """REQ: "For example, if we had a node containing the data 4, and we added the data 2, our tree would look like this:"

    Property: the first value inserted is the root node's data.
    """
    root = BinarySearchTree([4, 2, 6, 3, 1, 5, 7]).data()
    assert root.data == 4


def test_smaller_value_is_placed_in_left_subtree():
    """REQ: "All data in the left subtree is less than or equal to the current node's data, and all data in the right subtree is greater than the current node's data."

    Example: a node containing 4 with 2 added becomes 4 with left child 2 and no right child.
    """
    root = BinarySearchTree([4, 2]).data()
    assert root.data == 4
    assert root.left.data == 2
    assert root.right is None
    assert root.left.left is None
    assert root.left.right is None


def test_larger_value_is_placed_in_right_subtree():
    """REQ: "All data in the left subtree is less than or equal to the current node's data, and all data in the right subtree is greater than the current node's data."

    Example: a node containing 4 with 6 added becomes 4 with right child 6 and no left child.
    """
    root = BinarySearchTree([4, 6]).data()
    assert root.data == 4
    assert root.right.data == 6
    assert root.left is None
    assert root.right.left is None
    assert root.right.right is None


def test_third_level_insertion_example():
    """REQ: "If we then added 3, it would look like this"

    Example: from 4 with children 2 and 6, adding 3 places 3 as the right child of 2:
          4
        /   \\
       2     6
        \\
         3
    """
    root = BinarySearchTree([4, 2, 6, 3]).data()
    assert root.data == 4
    assert root.left.data == 2
    assert root.right.data == 6
    assert root.left.left is None
    assert root.left.right.data == 3
    assert root.left.right.left is None
    assert root.left.right.right is None
    assert root.right.left is None
    assert root.right.right is None


def test_full_example_tree_shape():
    """REQ: "And if we then added 1, 5, and 7, it would look like this"

    Example: inserting 4, 2, 6, 3, 1, 5, 7 gives a complete tree of seven nodes
    with leaves 1, 3, 5 and 7, each with nil children.
    """
    root = BinarySearchTree([4, 2, 6, 3, 1, 5, 7]).data()
    assert root.data == 4

    assert root.left.data == 2
    assert root.right.data == 6

    assert root.left.left.data == 1
    assert root.left.right.data == 3
    assert root.right.left.data == 5
    assert root.right.right.data == 7

    for leaf in (root.left.left, root.left.right, root.right.left, root.right.right):
        assert leaf.left is None
        assert leaf.right is None


def test_sorted_data_returns_values_in_ascending_order():
    """REQ: "Binary Search Trees, however, can operate on sorted data much more efficiently."

    Example: the tree built from 4, 2, 6, 3, 1, 5, 7 yields the values in ascending order.
    """
    result = BinarySearchTree([4, 2, 6, 3, 1, 5, 7]).sorted_data()
    assert result == [1, 2, 3, 4, 5, 6, 7]


def test_sorted_data_returns_a_list_matching_the_array_example():
    """REQ: "Say we have the array `[1, 3, 4, 5]`, and we add 2 to it so it becomes `[1, 3, 4, 5, 2]`."

    Property: sorted_data returns a list of the stored numbers in sorted order,
    using the array example with 2 added.
    """
    result = BinarySearchTree([1, 3, 4, 5, 2]).sorted_data()
    assert isinstance(result, list)
    assert result == [1, 2, 3, 4, 5]


def test_sorted_data_does_not_depend_on_insertion_order():
    """REQ: "Binary Search Trees, however, can operate on sorted data much more efficiently."

    Property: the same numbers inserted in different orders produce the same sorted output.
    """
    expected = [1, 2, 3, 4, 5, 6, 7]
    assert BinarySearchTree([4, 2, 6, 3, 1, 5, 7]).sorted_data() == expected
    assert BinarySearchTree([1, 2, 3, 4, 5, 6, 7]).sorted_data() == expected
    assert BinarySearchTree([7, 6, 5, 4, 3, 2, 1]).sorted_data() == expected


def test_duplicate_value_goes_to_left_subtree():
    """REQ: "All data in the left subtree is less than or equal to the current node's data, and all data in the right subtree is greater than the current node's data."

    Property: a value equal to the current node is placed in the left subtree.
    Example: inserting 2, 1, 2 gives root 2, left child 1, and 1's right child 2.
    """
    root = BinarySearchTree([2, 1, 2]).data()
    assert root.data == 2
    assert root.right is None
    assert root.left.data == 1
    assert root.left.left is None
    assert root.left.right.data == 2
    assert root.left.right.left is None
    assert root.left.right.right is None


def test_duplicate_values_are_kept_in_sorted_data():
    """REQ: "All data in the left subtree is less than or equal to the current node's data, and all data in the right subtree is greater than the current node's data."

    Property: duplicate values are all retained in sorted_data.
    """
    assert BinarySearchTree([2, 1, 2]).sorted_data() == [1, 2, 2]


def test_ordering_invariant_holds_at_every_node():
    """REQ: "All data in the left subtree is less than or equal to the current node's data, and all data in the right subtree is greater than the current node's data."

    Property: for a tree of distinct values, every node satisfies the ordering rule
    and no value is lost.
    """
    values = [5, 3, 8, 1, 4, 7, 9, 2, 6]
    root = BinarySearchTree(values).data()
    _assert_is_search_tree(root)
    assert _values(root) == sorted(values)


def test_ascending_input_builds_right_leaning_chain():
    """REQ: "All data in the right subtree is greater than the current node's data."

    Property: inserting in ascending order gives each new value as the right child
    of the previous one. Example: 1, 2, 3 gives 1 -> right 2 -> right 3.
    """
    root = BinarySearchTree([1, 2, 3]).data()
    assert root.data == 1
    assert root.left is None
    assert root.right.data == 2
    assert root.right.left is None
    assert root.right.right.data == 3
    assert root.right.right.left is None
    assert root.right.right.right is None


def test_descending_input_builds_left_leaning_chain():
    """REQ: "All data in the left subtree is less than or equal to the current node's data."

    Property: inserting in descending order gives each new value as the left child
    of the previous one. Example: 3, 2, 1 gives 3 -> left 2 -> left 1.
    """
    root = BinarySearchTree([3, 2, 1]).data()
    assert root.data == 3
    assert root.right is None
    assert root.left.data == 2
    assert root.left.right is None
    assert root.left.left.data == 1
    assert root.left.left.left is None
    assert root.left.left.right is None
