from mail import recipients

def test_order():
    assert recipients(['z@x', 'a@x', 'z@x']) == ['z@x', 'a@x']
