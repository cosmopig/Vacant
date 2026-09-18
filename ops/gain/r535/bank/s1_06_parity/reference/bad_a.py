def split_parity(xs):
    return {"even": [x for x in xs if x % 2 != 0],
            "odd": [x for x in xs if x % 2 == 0]}
