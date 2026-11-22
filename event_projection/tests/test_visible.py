from service import Projection

def test_apply_set():
    p = Projection()
    p.apply([{"id":"1","sku":"A","version":1,"kind":"set","quantity":3}])
    assert p.quantity("A") == 3
