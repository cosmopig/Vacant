def reserve(stock, sku, quantity):
    if 0 < quantity <= stock.get(sku, 0):
        stock[sku] -= quantity
        return True
    return False
