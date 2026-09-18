def format_money(cents):
    return "$%d.%02d" % divmod(cents, 100)
