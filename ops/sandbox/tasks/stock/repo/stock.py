def reserve(stock, sku, quantity):
    if stock.get(sku, 0) > quantity:
        stock[sku] -= quantity
        return True
    return False
