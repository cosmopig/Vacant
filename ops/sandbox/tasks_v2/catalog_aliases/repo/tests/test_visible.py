from service import Catalog

def test_catalog_lookup():
    catalog = Catalog()
    catalog.add("Tea", 250)
    assert catalog.lookup("tea")["price"] == 250
