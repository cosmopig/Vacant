from mail import recipients

def test_clean():
    assert recipients([' A@X ', '', 'a@x', '  ', 'b@x']) == ['A@X', 'b@x']
    assert recipients([]) == []
