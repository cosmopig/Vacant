def reserve(stock, sku, quantity):
    if quantity > 0 and stock.get(sku, 0) >= quantity:
        stock[sku] -= quantity
        return True
    return False
