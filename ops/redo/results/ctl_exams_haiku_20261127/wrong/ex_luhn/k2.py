class Luhn:
    def __init__(self, card_num):
        self.card_num = card_num

    def valid(self):
        stripped = self.card_num.replace(" ", "")
        if len(stripped) <= 1:
            return False
        if not all(ch in "0123456789" for ch in stripped):
            return False
        total = 0
        for i, ch in enumerate(reversed(stripped)):
            digit = int(ch)
            if i % 2 == 0:
                digit *= 2
                if digit > 9:
                    digit -= 9
            total += digit
        return total % 10 == 0
