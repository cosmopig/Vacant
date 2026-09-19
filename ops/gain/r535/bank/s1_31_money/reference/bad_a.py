def money(cents):
    return "$%d.%d" % divmod(cents, 100)
