from service import merge_roster

def test_merge_email():
    assert len(merge_roster([{"email":"a@b"}], [{"email":"A@B"}])) == 1
