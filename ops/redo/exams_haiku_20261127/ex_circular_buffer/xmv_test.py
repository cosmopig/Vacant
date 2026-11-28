import pytest

from circular_buffer import BufferEmptyException, BufferFullException, CircularBuffer


def test_elements_are_read_oldest_first():
    buf = CircularBuffer(7)
    buf.write(1)
    buf.write(2)
    buf.write(3)
    # SRC: "If two elements are then removed from the buffer, the oldest values inside the buffer are removed."
    assert buf.read() == 1
    # SRC: "The two elements removed, in this case, are 1 & 2, leaving the buffer with just a 3:"
    assert buf.read() == 2
    # SRC: "The two elements removed, in this case, are 1 & 2, leaving the buffer with just a 3:"
    assert buf.read() == 3


def test_buffer_of_length_seven_holds_seven_elements():
    buf = CircularBuffer(7)
    for value in range(7):
        buf.write(value)
    # SRC: "If the buffer has 7 elements then it is completely full:"
    with pytest.raises(BufferFullException):
        buf.write(7)


def test_write_to_full_buffer_raises_and_keeps_contents():
    buf = CircularBuffer(7)
    for value in [5, 6, 7, 8, 9, 3, 4]:
        buf.write(value)
    # SRC: "When the buffer is full an error will be raised, alerting the client that further writes are blocked until a slot becomes free."
    with pytest.raises(BufferFullException) as excinfo:
        buf.write(10)
    # SRC: "you should always include a **meaningful error message** to indicate what the source of the error is."
    assert str(excinfo.value) != ""
    # SRC: "When the buffer is full an error will be raised, alerting the client that further writes are blocked until a slot becomes free."
    assert buf.read() == 5


def test_read_from_empty_buffer_raises():
    buf = CircularBuffer(7)
    # SRC: "and one for when it is **empty**."
    with pytest.raises(BufferEmptyException):
        buf.read()


def test_read_after_all_elements_removed_raises():
    buf = CircularBuffer(7)
    buf.write(1)
    buf.read()
    # SRC: "and one for when it is **empty**."
    with pytest.raises(BufferEmptyException):
        buf.read()


def test_overwrite_on_full_buffer_replaces_oldest_elements():
    buf = CircularBuffer(7)
    for value in [5, 6, 7, 8, 9, 3, 4]:
        buf.write(value)
    buf.overwrite("A")
    buf.overwrite("B")
    # SRC: "3 & 4 have been replaced by A & B making 5 now the oldest data in the buffer."
    assert buf.read() == 5
    # SRC: "Finally, if two elements are removed then what would be returned is 5 & 6 yielding the buffer:"
    assert buf.read() == 6


def test_overwrite_after_reads_reuses_freed_slots_and_keeps_order():
    buf = CircularBuffer(7)
    for value in [5, 6, 7, 8, 9, 3, 4]:
        buf.write(value)
    buf.overwrite("A")
    buf.overwrite("B")
    buf.read()
    buf.read()
    buf.overwrite("C")
    buf.overwrite("D")
    # SRC: "7 is still the oldest element and the buffer is once again full."
    with pytest.raises(BufferFullException):
        buf.write(0)
    # SRC: "7 is still the oldest element and the buffer is once again full."
    assert buf.read() == 7
