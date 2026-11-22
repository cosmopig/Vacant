def charge_cents(units, price, free_units=0):
    billable = max(units - free_units, 0)
    return billable * price
