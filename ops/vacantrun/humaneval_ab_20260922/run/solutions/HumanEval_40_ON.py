def triples_sum_to_zero(l: list):
    """
    triples_sum_to_zero takes a list of integers as an input.
    it returns True if there are three distinct elements in the list that
    sum to zero, and False otherwise.

    >>> triples_sum_to_zero([1, 3, 5, 0])
    False
    >>> triples_sum_to_zero([1, 3, -2, 1])
    True
    >>> triples_sum_to_zero([1, 2, 3, 7])
    False
    >>> triples_sum_to_zero([2, 4, -5, 3, 9, 7])
    True
    >>> triples_sum_to_zero([1])
    False
    """
    n = len(l)
    if n < 3:
        return False

    pos = {}
    for i, val in enumerate(l):
        if val not in pos:
            pos[val] = []
        pos[val].append(i)

    for i in range(n):
        for j in range(i + 1, n):
            target = -(l[i] + l[j])
            if target in pos:
                for k in pos[target]:
                    if k != i and k != j:
                        return True
    return False
