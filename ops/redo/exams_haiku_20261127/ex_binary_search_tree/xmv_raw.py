import pytest

from binary_search_tree import TreeNode, BinarySearchTree


def test_single_node_holds_data_with_left_and_right_variables():
    tree = BinarySearchTree([4])
    root = tree.data()
    # SRC: "Each node contains a piece of data (e.g. the number 3), a variable named `left`, and a variable named `right`."
    assert root.data == 4


def test_single_node_left_and_right_point_at_nil():
    tree = BinarySearchTree([4])
    root = tree.data()
    # SRC: "The `left` and `right` variables point at `nil`, or other nodes."
    assert root.left is None
    # SRC: "The `left` and `right` variables point at `nil`, or other nodes."
    assert root.right is None


def test_adding_smaller_value_goes_to_left_child():
    tree = BinarySearchTree([4, 2])
    root = tree.data()
    # SRC: "if we had a node containing the data 4, and we added the data 2, our tree would look like this:"
    assert root.data == 4
    # SRC: "if we had a node containing the data 4, and we added the data 2, our tree would look like this:"
    assert root.left.data == 2
    # SRC: "if we had a node containing the data 4, and we added the data 2, our tree would look like this:"
    assert root.right is None


def test_adding_greater_value_goes_to_right_child():
    tree = BinarySearchTree([4, 2, 6])
    root = tree.data()
    # SRC: "If we then added 6, it would look like this:"
    assert root.right.data == 6
    # SRC: "If we then added 6, it would look like this:"
    assert root.right.left is None
    # SRC: "If we then added 6, it would look like this:"
    assert root.right.right is None


def test_adding_value_between_root_and_left_child_becomes_right_grandchild():
    tree = BinarySearchTree([4, 2, 6, 3])
    root = tree.data()
    # SRC: "If we then added 3, it would look like this"
    assert root.left.right.data == 3
    # SRC: "If we then added 3, it would look like this"
    assert root.left.left is None


def test_full_example_tree_structure():
    tree = BinarySearchTree([4, 2, 6, 1, 3, 5, 7])
    root = tree.data()
    # SRC: "And if we then added 1, 5, and 7, it would look like this"
    assert root.data == 4
    # SRC: "And if we then added 1, 5, and 7, it would look like this"
    assert root.left.data == 2
    # SRC: "And if we then added 1, 5, and 7, it would look like this"
    assert root.right.data == 6
    # SRC: "And if we then added 1, 5, and 7, it would look like this"
    assert root.left.left.data == 1
    # SRC: "And if we then added 1, 5, and 7, it would look like this"
    assert root.left.right.data == 3
    # SRC: "And if we then added 1, 5, and 7, it would look like this"
    assert root.right.left.data == 5
    # SRC: "And if we then added 1, 5, and 7, it would look like this"
    assert root.right.right.data == 7


def test_equal_value_goes_to_left_subtree():
    tree = BinarySearchTree([4, 4])
    root = tree.data()
    # SRC: "All data in the left subtree is less than or equal to the current node's data, and all data in the right subtree is greater than the current node's data."
    assert root.left.data == 4
    # SRC: "All data in the left subtree is less than or equal to the current node's data, and all data in the right subtree is greater than the current node's data."
    assert root.right is None


def test_equal_value_in_right_subtree_goes_to_left_of_that_node():
    tree = BinarySearchTree([4, 6, 6])
    root = tree.data()
    # SRC: "All data in the left subtree is less than or equal to the current node's data, and all data in the right subtree is greater than the current node's data."
    assert root.right.data == 6
    # SRC: "All data in the left subtree is less than or equal to the current node's data, and all data in the right subtree is greater than the current node's data."
    assert root.right.left.data == 6
    # SRC: "All data in the left subtree is less than or equal to the current node's data, and all data in the right subtree is greater than the current node's data."
    assert root.right.right is None


def test_sorted_data_returns_values_in_ascending_order():
    tree = BinarySearchTree([4, 2, 6, 1, 3, 5, 7])
    # SRC: "All data in the left subtree is less than or equal to the current node's data, and all data in the right subtree is greater than the current node's data."
    assert tree.sorted_data() == [1, 2, 3, 4, 5, 6, 7]


def test_sorted_data_keeps_duplicates():
    tree = BinarySearchTree([4, 4, 2])
    # SRC: "All data in the left subtree is less than or equal to the current node's data, and all data in the right subtree is greater than the current node's data."
    assert tree.sorted_data() == [2, 4, 4]
