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
        self._read_index = 0
        self._write_index = 0
        self._count = 0

    def read(self):
        if self._count == 0:
            raise BufferEmptyException("Circular buffer is empty")
        data = self._buffer[self._read_index]
        self._buffer[self._read_index] = None
        self._read_index = (self._read_index + 1) % self._capacity
        self._count -= 1
        return data

    def write(self, data):
        if self._count == self._capacity:
            raise BufferFullException("Circular buffer is full")
        self._buffer[self._write_index] = data
        self._write_index = (self._write_index + 1) % self._capacity
        self._count += 1

    def overwrite(self, data):
        if self._count == self._capacity:
            self._buffer[self._write_index] = data
            self._write_index = (self._write_index + 1) % self._capacity
            self._read_index = self._write_index
        else:
            self.write(data)

    def clear(self):
        self._count = 0
