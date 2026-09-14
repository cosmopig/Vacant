"""Known-bad C: the skeleton. Every name exists, almost nothing happens."""
def matches(pattern, path):
    return pattern == path


def select(patterns, paths):
    return [path for path in paths if path in patterns]
