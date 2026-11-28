class Luhn:
    def __init__(self, card_num):
        self.card_num = card_num

    def valid(self):
        digits = self.card_num.replace(" ", "")
        if len(digits) < 1 or not all(c in "0123456789" for c in digits):
            return False
        total = 0
        for i, ch in enumerate(reversed(digits)):
            d = int(ch)
            if i % 2 == 1:
                d *= 2
                if d > 9:
                    d -= 9
            total += d
        return total % 10 == 0
