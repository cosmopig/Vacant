"""Reference solution for ow_07_retrypolicy (gauge only; never enters a workspace)."""


def delay_after(failure_number, backoff_s, max_backoff_s):
    """Seconds to wait after the failure_number-th failure, counting from 1."""
    return min(backoff_s * 2 ** (failure_number - 1), max_backoff_s)


def retry(fn, *, attempts, backoff_s, max_backoff_s, retry_on, sleep):
    if attempts < 1:
        raise ValueError("attempts must be at least 1, got %r" % (attempts,))
    for number in range(1, attempts + 1):
        try:
            return fn()
        except BaseException as failure:
            # isinstance against an empty tuple is False, which is exactly the
            # "an empty retry_on retries nothing" rule -- no special case needed.
            if not isinstance(failure, tuple(retry_on)):
                raise
            if number == attempts:
                raise
            sleep(delay_after(number, backoff_s, max_backoff_s))
