class TreeNode:
    def __init__(self, data, left=None, right=None):
        self.data = data
        self.left = left
        self.right = right

    def __str__(self):
        return f'TreeNode(data={self.data}, left={self.left}, right={self.right})'


class BinarySearchTree:
    def __init__(self, tree_data):
        self.root = None
        for value in tree_data:
            self._insert(value)

    def _insert(self, value):
        new_node = TreeNode(value)
        if self.root is None:
            self.root = new_node
            return
        current = self.root
        while True:
            if value <= current.data:
                if current.left is None:
                    current.left = new_node
                    return
                current = current.left
            else:
                if current.right is None:
                    current.right = new_node
                    return
                current = current.right

    def _node_to_dict(self, node):
        if node is None:
            return None
        return {
            'data': node.data,
            'left': self._node_to_dict(node.left),
            'right': self._node_to_dict(node.right),
        }

    def data(self):
        if self.root is None:
            return {'data': None, 'left': None, 'right': None}
        return self._node_to_dict(self.root)

    def _in_order(self, node, result):
        if node is None:
            return
        self._in_order(node.left, result)
        result.append(node.data)
        self._in_order(node.right, result)

    def sorted_data(self):
        result = []
        self._in_order(self.root, result)
        return tuple(result)
