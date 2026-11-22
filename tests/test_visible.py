from service import Manifest

def test_add_manifest():
    m = Manifest()
    m.add("file.txt", 3, "a"*64)
    assert m.total_size() == 3
