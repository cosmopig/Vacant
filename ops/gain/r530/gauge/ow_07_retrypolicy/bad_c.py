"""Known-bad C: the skeleton. Every name exists, almost nothing happens."""
def retry(fn, *, attempts, backoff_s, max_backoff_s, retry_on, sleep):
    return fn()
