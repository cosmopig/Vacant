from binary_search_tree import BinarySearchTree


def test_single_element_tree_root_has_no_children():
    root = BinarySearchTree([4]).data()
    assert root.data == 4
    assert root.left is None
    assert root.right is None


def test_smaller_value_is_inserted_to_the_left():
    root = BinarySearchTree([4, 2]).data()
    assert root.data == 4
    assert root.left.data == 2
    assert root.right is None


def test_greater_value_is_inserted_to_the_right():
    root = BinarySearchTree([4, 6]).data()
    assert root.data == 4
    assert root.left is None
    assert root.right.data == 6


def test_smaller_value_after_greater_value_goes_left_of_root():
    root = BinarySearchTree([4, 6, 2]).data()
    assert root.data == 4
    assert root.left.data == 2
    assert root.right.data == 6


def test_third_level_value_goes_right_of_left_child():
    root = BinarySearchTree([4, 2, 6, 3]).data()
    assert root.data == 4
    assert root.left.data == 2
    assert root.left.right.data == 3
    assert root.left.left is None
    assert root.right.data == 6
    assert root.right.left is None
    assert root.right.right is None


def test_full_example_tree_structure():
    root = BinarySearchTree([4, 2, 6, 1, 3, 5, 7]).data()
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


def test_equal_value_goes_to_the_left():
    root = BinarySearchTree([2, 2]).data()
    assert root.data == 2
    assert root.left.data == 2
    assert root.right is None


def test_equal_value_below_root_goes_left_of_that_node():
    root = BinarySearchTree([5, 3, 3]).data()
    assert root.data == 5
    assert root.left.data == 3
    assert root.left.left.data == 3
    assert root.left.right is None


def test_insertion_order_determines_shape():
    root = BinarySearchTree([1, 2, 3]).data()
    assert root.data == 1
    assert root.left is None
    assert root.right.data == 2
    assert root.right.left is None
    assert root.right.right.data == 3


def test_sorted_data_of_single_element():
    assert BinarySearchTree([4]).sorted_data() == [4]


def test_sorted_data_of_full_example():
    assert BinarySearchTree([4, 2, 6, 1, 3, 5, 7]).sorted_data() == [1, 2, 3, 4, 5, 6, 7]


def test_sorted_data_keeps_duplicates_in_order():
    assert BinarySearchTree([5, 3, 3, 8]).sorted_data() == [3, 3, 5, 8]


def test_sorted_data_with_negative_numbers():
    assert BinarySearchTree([0, -3, 7, -10, 2]).sorted_data() == [-10, -3, 0, 2, 7]
