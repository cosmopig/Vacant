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
        node = self.head
        while node is not None:
            yield node.value
            node = node.succeeding

    def push(self, value):
        node = Node(value, previous=self.tail)
        if self.tail is None:
            self.head = node
        else:
            self.tail.succeeding = node
        self.tail = node
        self.length += 1

    def pop(self):
        if self.tail is None:
            raise IndexError("List is empty")
        node = self.tail
        self.tail = node.previous
        if self.tail is None:
            self.head = None
        else:
            self.tail.succeeding = None
        self.length -= 1
        return node.value

    def unshift(self, value):
        node = Node(value, succeeding=self.head)
        if self.head is None:
            self.tail = node
        else:
            self.head.previous = node
        self.head = node
        self.length += 1

    def shift(self):
        if self.head is None:
            raise IndexError("List is empty")
        node = self.head
        self.head = node.succeeding
        if self.head is None:
            self.tail = None
        else:
            self.head.previous = None
        self.length -= 1
        return node.value

    def delete(self, value):
        node = self.head
        while node is not None:
            if node.value == value:
                break
            node = node.succeeding
        else:
            raise ValueError("Value not found")
        if node.previous is None:
            self.head = node.succeeding
        else:
            node.previous.succeeding = node.succeeding
        if node.succeeding is not None:
            node.succeeding.previous = node.previous
        self.length -= 1
