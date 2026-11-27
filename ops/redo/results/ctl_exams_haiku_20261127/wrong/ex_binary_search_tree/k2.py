class TreeNode:
    def __init__(self, data, left=None, right=None):
        self.data = data
        self.left = left
        self.right = right

    def __str__(self):
        return f'TreeNode(data={self.data}, left={self.left}, right={self.right})'


class BinarySearchTree:
    def __init__(self, tree_data):
        self._root = None
        for value in tree_data:
            self._insert(value)

    def _insert(self, value):
        if self._root is None:
            self._root = TreeNode(value)
            return
        node = self._root
        while True:
            if value < node.data:
                if node.left is None:
                    node.left = TreeNode(value)
                    return
                node = node.left
            else:
                if node.right is None:
                    node.right = TreeNode(value)
                    return
                node = node.right

    def data(self):
        return self._root

    def sorted_data(self):
        result = []

        def walk(node):
            if node is None:
                return
            walk(node.left)
            result.append(node.data)
            walk(node.right)

        walk(self._root)
        return result
