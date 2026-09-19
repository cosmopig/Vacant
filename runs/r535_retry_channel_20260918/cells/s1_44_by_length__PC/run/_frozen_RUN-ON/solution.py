def by_length(words: list[str]) -> list[str]:
    # Python's sort is stable, so we only need to sort by length.
    return sorted(words, key=len)
