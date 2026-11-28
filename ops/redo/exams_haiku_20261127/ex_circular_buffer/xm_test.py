import pytest

from circular_buffer import BufferEmptyException, BufferFullException, CircularBuffer


def _message(exc):
    """Return the exception's message, whether it is stored in str(exc) or in .message."""
    return str(exc) or getattr(exc, "message", "")


def test_exceptions_are_buffer_errors():
    assert issubclass(BufferFullException, BufferError)
    assert issubclass(BufferEmptyException, BufferError)


def test_write_then_read_returns_element():
    buf = CircularBuffer(1)
    buf.write(1)
    assert buf.read() == 1


def test_read_returns_oldest_first():
    buf = CircularBuffer(3)
    buf.write(1)
    buf.write(2)
    assert buf.read() == 1
    assert buf.read() == 2


def test_spec_example_removing_two_leaves_three():
    buf = CircularBuffer(7)
    buf.write(1)
    buf.write(2)
    buf.write(3)
    assert buf.read() == 1
    assert buf.read() == 2
    assert buf.read() == 3
    with pytest.raises(BufferEmptyException):
        buf.read()


def test_read_from_empty_buffer_raises_with_message():
    buf = CircularBuffer(2)
    with pytest.raises(BufferEmptyException) as excinfo:
        buf.read()
    assert _message(excinfo.value).strip() != ""


def test_write_to_full_buffer_raises_with_message():
    buf = CircularBuffer(2)
    buf.write(1)
    buf.write(2)
    with pytest.raises(BufferFullException) as excinfo:
        buf.write(3)
    assert _message(excinfo.value).strip() != ""


def test_full_buffer_still_yields_original_elements_after_failed_write():
    buf = CircularBuffer(2)
    buf.write(1)
    buf.write(2)
    with pytest.raises(BufferFullException):
        buf.write(3)
    assert buf.read() == 1
    assert buf.read() == 2


def test_overwrite_on_full_buffer_replaces_oldest():
    buf = CircularBuffer(3)
    buf.write(1)
    buf.write(2)
    buf.write(3)
    buf.overwrite(4)
    assert buf.read() == 2
    assert buf.read() == 3
    assert buf.read() == 4


def test_overwrite_on_non_full_buffer_acts_like_write():
    buf = CircularBuffer(3)
    buf.write(1)
    buf.overwrite(2)
    assert buf.read() == 1
    assert buf.read() == 2


def test_overwrite_on_empty_buffer_stores_element():
    buf = CircularBuffer(2)
    buf.overwrite(7)
    assert buf.read() == 7


def test_spec_overwrite_example_reuses_freed_slots():
    buf = CircularBuffer(7)
    for value in (3, 4, 5, 6, 7, 8, 9):
        buf.write(value)
    with pytest.raises(BufferFullException):
        buf.write(0)

    buf.overwrite(10)
    buf.overwrite(11)
    assert buf.read() == 5
    assert buf.read() == 6

    buf.overwrite(12)
    buf.overwrite(13)
    assert buf.read() == 7
    assert buf.read() == 8
    assert buf.read() == 9
    assert buf.read() == 10
    assert buf.read() == 11
    assert buf.read() == 12
    assert buf.read() == 13
    with pytest.raises(BufferEmptyException):
        buf.read()


def test_wraparound_after_reads_keeps_fifo_order():
    buf = CircularBuffer(2)
    buf.write(1)
    assert buf.read() == 1
    buf.write(2)
    buf.write(3)
    assert buf.read() == 2
    assert buf.read() == 3


def test_clear_empties_buffer():
    buf = CircularBuffer(2)
    buf.write(1)
    buf.write(2)
    buf.clear()
    with pytest.raises(BufferEmptyException):
        buf.read()


def test_buffer_is_usable_after_clear():
    buf = CircularBuffer(2)
    buf.write(1)
    buf.write(2)
    buf.clear()
    buf.write(3)
    assert buf.read() == 3


def test_clear_frees_full_buffer_for_writes():
    buf = CircularBuffer(1)
    buf.write(1)
    with pytest.raises(BufferFullException):
        buf.write(2)
    buf.clear()
    buf.write(2)
    assert buf.read() == 2


def test_capacity_one_overwrite_keeps_latest():
    buf = CircularBuffer(1)
    buf.overwrite(1)
    buf.overwrite(2)
    assert buf.read() == 2
    with pytest.raises(BufferEmptyException):
        buf.read()
