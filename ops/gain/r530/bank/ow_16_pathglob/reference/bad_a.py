"""Known-bad A: fnmatch and nothing else.

fnmatch's star happily crosses directory levels, there is no double star, and an
exclamation mark is just a character in the pattern.
"""

import fnmatch


def matches(pattern, path):
    return fnmatch.fnmatch(path, pattern)


def select(patterns, paths):
    out = []
    for pattern in patterns:
        for path in paths:
            if fnmatch.fnmatch(path, pattern) and path not in out:
                out.append(path)
    return out
