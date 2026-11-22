"""Account transfer service and cached read model."""
from decimal import Decimal, ROUND_HALF_EVEN
from checks import number, snapshot

CENT = Decimal("0.01")


def money(value):
    result = number(value, "amount").quantize(CENT, rounding=ROUND_HALF_EVEN)
    return result if result else CENT * 0


class Ledger:
    def __init__(self, opening):
        self._balances = {name: money(value) for name, value in opening.items()}
        if any(value < 0 for value in self._balances.values()):
            raise ValueError("negative opening balance")
        self._cache = {}
        self._keys = {}

    def accounts(self):
        return tuple(sorted(self._balances))

    def balance(self, name):
        if name not in self._cache:
            self._cache[name] = self._balances[name]
        return self._cache[name]

    def transfer(self, source, target, amount, key=None):
        amount = money(amount)
        for account in (source, target):
            if account not in self._balances:
                raise KeyError(account)
        if source == target:
            raise ValueError("accounts must differ")
        if amount <= 0:
            raise ValueError("amount must be positive")
        request = (source, target, amount)
        if key is not None and key in self._keys:
            if self._keys[key] != request:
                raise ValueError("key conflict")
            return
        if self._balances[source] < amount:
            raise ValueError("insufficient funds")
        self._balances[source] -= amount
        self._balances[target] += amount
        self._cache.pop(source, None)
        self._cache.pop(target, None)
        if key is not None:
            self._keys[key] = request

    def snapshot(self):
        return snapshot({name: str(self.balance(name)) for name in self.accounts()})

    def history(self):
        return snapshot({key: [a, b, str(value)] for key, (a, b, value) in self._keys.items()})

    def total(self):
        return sum((self.balance(name) for name in self.accounts()), Decimal("0.00"))
