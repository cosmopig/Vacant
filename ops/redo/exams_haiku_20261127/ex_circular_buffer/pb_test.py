"""Acceptance tests for the circular buffer exercise.

Each test_ function checks one property taken from the requirements text.
Expected values are derived by hand from the requirements.
"""
from circular_buffer import (
    BufferEmptyException,
    BufferFullException,
    CircularBuffer,
)


def _error_raised_by(action):
    """Return the exception raised by calling action(), or None if nothing was raised."""
    try:
        action()
    except Exception as error:
        return error
    return None


def _message_of(error):
    """Return the message carried by an exception, preferring a .message attribute."""
    message = getattr(error, "message", None)
    if not message:
        message = str(error)
    return message


def test_new_buffer_starts_empty():
    """REQ: "A circular buffer first starts empty and of some predefined length."

    Property: a freshly created buffer holds no data, so reading raises BufferEmptyException.
    """
    buf = CircularBuffer(3)
    error = _error_raised_by(buf.read)
    assert isinstance(error, BufferEmptyException)


def test_empty_exception_subclasses_builtin_buffer_error():
    """REQ: "To customize a `built-in exception`, create a `class` that inherits from that exception."

    Property: BufferEmptyException is a subclass of the built-in BufferError.
    """
    assert issubclass(BufferEmptyException, BufferError)


def test_full_exception_subclasses_builtin_buffer_error():
    """REQ: "To customize a `built-in exception`, create a `class` that inherits from that exception."

    Property: BufferFullException is a subclass of the built-in BufferError.
    """
    assert issubclass(BufferFullException, BufferError)


def test_full_and_empty_exceptions_are_distinct():
    """REQ: "One exception to be raised when your circular buffer is full, and one for when it is empty."

    Property: the full and empty exceptions are different types, neither a subclass of the other.
    """
    assert not issubclass(BufferFullException, BufferEmptyException)
    assert not issubclass(BufferEmptyException, BufferFullException)


def test_read_returns_written_element():
    """REQ: "Assume that a 1 is written into the middle of the buffer (exact starting location does not matter in a circular buffer)."

    Property: writing a value and then reading returns that same value.
    """
    buf = CircularBuffer(7)
    buf.write(1)
    assert buf.read() == 1


def test_read_removes_element_so_next_read_is_empty():
    """REQ: "If two elements are then removed from the buffer, the oldest values inside the buffer are removed."

    Property: a read removes the element, so a second read on the now-empty buffer raises BufferEmptyException.
    """
    buf = CircularBuffer(7)
    buf.write(1)
    assert buf.read() == 1
    error = _error_raised_by(buf.read)
    assert isinstance(error, BufferEmptyException)


def test_reads_remove_oldest_values_first():
    """REQ: "The two elements removed, in this case, are 1 & 2, leaving the buffer with just a 3:"

    Property: after writing 1, 2, 3, reads return 1, then 2, then 3, and a further read raises BufferEmptyException.
    """
    buf = CircularBuffer(7)
    for value in (1, 2, 3):
        buf.write(value)
    assert buf.read() == 1
    assert buf.read() == 2
    assert buf.read() == 3
    error = _error_raised_by(buf.read)
    assert isinstance(error, BufferEmptyException)


def test_buffer_of_seven_is_full_after_seven_writes():
    """REQ: "If the buffer has 7 elements then it is completely full:"

    Property: a 7-element buffer accepts exactly 7 writes; the 8th write raises BufferFullException.
    """
    buf = CircularBuffer(7)
    for value in range(1, 8):
        assert _error_raised_by(lambda v=value: buf.write(v)) is None
    error = _error_raised_by(lambda: buf.write(8))
    assert isinstance(error, BufferFullException)


def test_write_to_full_buffer_raises_full_exception():
    """REQ: "When the buffer is full an error will be raised, alerting the client that further writes are blocked until a slot becomes free."

    Property: writing to a full buffer raises BufferFullException.
    """
    buf = CircularBuffer(2)
    buf.write("a")
    buf.write("b")
    error = _error_raised_by(lambda: buf.write("c"))
    assert isinstance(error, BufferFullException)


def test_rejected_write_leaves_contents_unchanged():
    """REQ: "further writes are blocked until a slot becomes free."

    Property: a write rejected because the buffer is full does not change the stored data.
    """
    buf = CircularBuffer(2)
    buf.write("a")
    buf.write("b")
    _error_raised_by(lambda: buf.write("c"))
    assert buf.read() == "a"
    assert buf.read() == "b"


def test_exception_messages_are_meaningful():
    """REQ: "When raising the error, you should still include a meaningful message."

    Property: both the full and empty exceptions carry a non-empty message.
    """
    full_buf = CircularBuffer(1)
    full_buf.write("x")
    full_error = _error_raised_by(lambda: full_buf.write("y"))
    assert isinstance(full_error, BufferFullException)
    full_message = _message_of(full_error)
    assert isinstance(full_message, str)
    assert full_message.strip() != ""

    empty_buf = CircularBuffer(1)
    empty_error = _error_raised_by(empty_buf.read)
    assert isinstance(empty_error, BufferEmptyException)
    empty_message = _message_of(empty_error)
    assert isinstance(empty_message, str)
    assert empty_message.strip() != ""


def test_overwrite_on_full_buffer_replaces_oldest_values():
    """REQ: "In this case, two more elements — A & B — are added and they overwrite the 3 & 4:"

    Property: overwriting a full buffer replaces the oldest values; the oldest remaining value becomes 5.
    """
    buf = CircularBuffer(7)
    for value in (3, 4, 5, 6, 7, 8, 9):
        buf.write(value)
    buf.overwrite("A")
    buf.overwrite("B")
    assert [buf.read() for _ in range(7)] == [5, 6, 7, 8, 9, "A", "B"]


def test_overwrite_on_full_buffer_does_not_raise():
    """REQ: "When the buffer is full, the client can opt to overwrite the oldest data with a forced write."

    Property: overwrite on a full buffer succeeds without raising, and the oldest value is discarded.
    """
    buf = CircularBuffer(2)
    buf.write("a")
    buf.write("b")
    error = _error_raised_by(lambda: buf.overwrite("c"))
    assert error is None
    assert buf.read() == "b"
    assert buf.read() == "c"


def test_overwrite_reuses_freed_slots_and_refills_buffer():
    """REQ: "Because there is space available, if the client again uses overwrite to store C & D then the space where 5 & 6 were stored previously will be used not the location of 7 & 8."

    Property: after the buffer holds 7,8,9,A,B with two free slots, overwriting C and D keeps the order 7,8,9,A,B,C,D
    and leaves the buffer full again.
    """
    buf = CircularBuffer(7)
    for value in (3, 4, 5, 6, 7, 8, 9):
        buf.write(value)
    buf.overwrite("A")
    buf.overwrite("B")
    assert buf.read() == 5
    assert buf.read() == 6
    buf.overwrite("C")
    buf.overwrite("D")
    error = _error_raised_by(lambda: buf.write("E"))
    assert isinstance(error, BufferFullException)
    assert [buf.read() for _ in range(7)] == [7, 8, 9, "A", "B", "C", "D"]


def test_overwrite_when_space_available_keeps_existing_data():
    """REQ: "Because there is space available, if the client again uses overwrite to store C & D then the space where 5 & 6 were stored previously will be used not the location of 7 & 8."

    Property: overwrite on a buffer that has free space does not raise and does not discard existing data.
    """
    buf = CircularBuffer(3)
    buf.write(1)
    error = _error_raised_by(lambda: buf.overwrite(2))
    assert error is None
    assert buf.read() == 1
    assert buf.read() == 2
    assert isinstance(_error_raised_by(buf.read), BufferEmptyException)


def test_fifo_order_holds_across_wrap_around():
    """REQ: "When the buffer is full an error will be raised, alerting the client that further writes are blocked until a slot becomes free."

    Property: once a read frees a slot, a write succeeds and values still come out in insertion order.
    """
    buf = CircularBuffer(3)
    buf.write(1)
    buf.write(2)
    buf.write(3)
    assert buf.read() == 1
    error = _error_raised_by(lambda: buf.write(4))
    assert error is None
    assert buf.read() == 2
    assert buf.read() == 3
    assert buf.read() == 4


def test_capacity_one_buffer_boundary():
    """REQ: "A circular buffer first starts empty and of some predefined length."

    Property: a buffer of capacity 1 is full after one write, and accepts another write once its single element is read.
    """
    buf = CircularBuffer(1)
    buf.write("a")
    error = _error_raised_by(lambda: buf.write("b"))
    assert isinstance(error, BufferFullException)
    assert buf.read() == "a"
    error = _error_raised_by(lambda: buf.write("b"))
    assert error is None
    assert buf.read() == "b"


def test_read_returns_value_unchanged_in_type():
    """REQ: "Assume that a 1 is written into the middle of the buffer (exact starting location does not matter in a circular buffer)."

    Property: the value returned by read equals the value written, and keeps its type, for int, str and float data.
    """
    buf = CircularBuffer(3)
    buf.write(42)
    buf.write("text")
    buf.write(2.5)
    first = buf.read()
    second = buf.read()
    third = buf.read()
    assert first == 42 and isinstance(first, int)
    assert second == "text" and isinstance(second, str)
    assert third == 2.5 and isinstance(third, float)
