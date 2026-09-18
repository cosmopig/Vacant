def parse_int(s):
    try:
        return int(str(s).strip())
    except ValueError:
        return None
