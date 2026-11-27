class BufferFullException(BufferError):
    """Exception raised when CircularBuffer is full.

    message: explanation of the error.

    """
    def __init__(self, message):
        self.message = message
        super().__init__(message)


class BufferEmptyException(BufferError):
    """Exception raised when CircularBuffer is empty.

    message: explanation of the error.

    """
    def __init__(self, message):
        self.message = message
        super().__init__(message)


class CircularBuffer:
    def __init__(self, capacity):
        self._capacity = capacity
        self._buffer = [None] * capacity
        self._head = 0
        self._tail = 0
        self._size = 0

    def read(self):
        if self._size == 0:
            raise BufferEmptyException("Circular buffer is empty")
        value = self._buffer[self._head]
        self._buffer[self._head] = None
        self._head = (self._head + 1) % self._capacity
        self._size -= 1
        return str(value)

    def write(self, data):
        if self._size == self._capacity:
            raise BufferFullException("Circular buffer is full")
        self._buffer[self._tail] = data
        self._tail = (self._tail + 1) % self._capacity
        self._size += 1

    def overwrite(self, data):
        if self._size == self._capacity:
            self._buffer[self._tail] = data
            self._tail = (self._tail + 1) % self._capacity
            self._head = self._tail
        else:
            self.write(data)

    def clear(self):
        self._buffer = [None] * self._capacity
        self._head = 0
        self._tail = 0
        self._size = 0
