from service import quote

def test_graduated_quote():
    assert quote(12, [(10,"2"),(None,"1")]) == "22.00"
