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
        self.capacity = capacity
        self._buffer = [None] * capacity
        self._read = 0
        self._write = 0
        self._count = 0

    def read(self):
        if self._count == 0:
            raise BufferEmptyException("Circular buffer is empty")
        data = self._buffer[self._read]
        self._buffer[self._read] = None
        self._read = (self._read + 1) % self.capacity
        self._count -= 1
        return data

    def write(self, data):
        if self._count == self.capacity:
            raise BufferFullException("Circular buffer is full")
        self._buffer[self._write] = data
        self._write = (self._write + 1) % self.capacity
        self._count += 1

    def overwrite(self, data):
        if self._count > 0:
            self.read()
        self.write(data)

    def clear(self):
        self._buffer = [None] * self.capacity
        self._read = 0
        self._write = 0
        self._count = 0
