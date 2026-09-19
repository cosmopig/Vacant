def initials(name):
    import re
    parts = name.split(' ')
    initials_list = []
    for part in parts:
        if not part:
            continue
        segments = re.split(r'[-.,;:]', part)
        for segment in segments:
            if segment:
                initials_list.append(segment[0].upper())
    return "".join(initials_list)

def test_initials():
    assert initials('ada lovelace') == 'A.L.'
    assert initials('jean-luc picard') == 'J.L.P.'

if __name__ == "__main__":
    test_initials()
