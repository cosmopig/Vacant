from service import summarize

def test_one_sale():
    assert summarize([{"merchant":"A","currency":"USD","amount":"2"}])[0]["total"] == "2.00"
