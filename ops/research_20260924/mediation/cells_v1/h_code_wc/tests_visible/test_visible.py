from solution import word_count

def check_a():
    assert word_count('a A b.') == {'a': 2, 'b': 1}
