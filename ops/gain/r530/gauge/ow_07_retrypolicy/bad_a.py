"""Known-bad A: retries everything, sleeps at the end, wraps the failure.

Three habits that travel together: catching Exception rather than the listed
types, sleeping after the last attempt as part of the loop body, and raising a
new RuntimeError so the caller loses the original.
"""


def retry(fn, *, attempts, backoff_s, max_backoff_s, retry_on, sleep):
    last = None
    for number in range(attempts):
        try:
            return fn()
        except Exception as failure:
            last = failure
            sleep(backoff_s * 2 ** number)
    raise RuntimeError("gave up after %d attempts: %s" % (attempts, last))
