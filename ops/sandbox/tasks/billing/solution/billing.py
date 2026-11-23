def charge_cents(units, price, free_units=0):
    return max(0, units - free_units) * price
