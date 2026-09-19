from solution import size_label

def test_size_label():
    assert size_label(500) == '500 B'
    assert size_label(1024) == '1 KB'
    assert size_label(1536) == '1.5 KB'
    assert size_label(1048576) == '1 MB'
    assert size_label(1073741824) == '1 GB'

if __name__ == "__main__":
    test_size_label()
