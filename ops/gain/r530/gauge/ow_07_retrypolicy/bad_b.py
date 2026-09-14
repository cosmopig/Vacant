"""Known-bad B: the right shape with an off-by-one and an exact type check.

The injected sleep is used and the original error is re-raised, but the first wait
is already doubled, the ceiling is never applied, and the failure is matched by
exact type instead of by instance.
"""


def retry(fn, *, attempts, backoff_s, max_backoff_s, retry_on, sleep):
    if attempts < 1:
        raise ValueError("attempts must be at least 1")
    for number in range(1, attempts + 1):
        try:
            return fn()
        except BaseException as failure:
            if type(failure) not in tuple(retry_on):
                raise
            if number == attempts:
                raise
            sleep(backoff_s * 2 ** number)
