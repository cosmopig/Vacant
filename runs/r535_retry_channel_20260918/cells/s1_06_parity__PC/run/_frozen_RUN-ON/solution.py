def split_parity(xs):
    even = []
    odd = []
    for x in xs:
        if x % 2 == 0:
            even.append(x)
        else:
            odd.append(x)
    return {"even": even, "odd": odd}
