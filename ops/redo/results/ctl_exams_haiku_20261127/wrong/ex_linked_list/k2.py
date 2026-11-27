class Node:
    def __init__(self, value, succeeding=None, previous=None):
        self.value = value
        self.succeeding = succeeding
        self.previous = previous


class LinkedList:
    def __init__(self):
        self.head = None
        self.tail = None
        self.length = 0

    def __len__(self):
        return self.length

    def __iter__(self):
        current = self.head
        while current is not None:
            yield current.value
            current = current.succeeding

    def _unlink(self, node):
        if node.previous is not None:
            node.previous.succeeding = node.succeeding
        else:
            self.head = node.succeeding
        if node.succeeding is not None:
            node.succeeding.previous = node.previous
        else:
            self.tail = node.previous
        node.succeeding = None
        node.previous = None
        self.length -= 1
        return node.value

    def push(self, value):
        node = Node(value, None, self.tail)
        if self.tail is not None:
            self.tail.succeeding = node
        else:
            self.head = node
        self.tail = node
        self.length += 1

    def pop(self):
        if self.length == 0:
            raise IndexError("List is empty")
        return self._unlink(self.tail)

    def unshift(self, value):
        node = Node(value, self.head, None)
        if self.head is not None:
            self.head.previous = node
        else:
            self.tail = node
        self.head = node
        self.length += 1

    def shift(self):
        if self.length == 0:
            raise IndexError("List is empty")
        return self._unlink(self.head)

    def delete(self, value):
        current = self.tail
        while current is not None:
            if current.value == value:
                self._unlink(current)
                return
            current = current.previous
        raise ValueError("Value not found")
