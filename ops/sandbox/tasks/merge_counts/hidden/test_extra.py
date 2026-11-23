from counts import merge_counts

def test_merge():
    a = {'a': 2, 'b': -1}
    assert merge_counts(a, {'a': -2, 'c': 4}) == {'a': 0, 'b': -1, 'c': 4}
    assert a == {'a': 2, 'b': -1}
