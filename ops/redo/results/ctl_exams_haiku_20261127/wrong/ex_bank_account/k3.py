class BankAccount:
    def __init__(self):
        self._open = False
        self._balance = 0

    def get_balance(self):
        if not self._open:
            raise ValueError('account not open')
        return float(self._balance)

    def open(self):
        if self._open:
            raise ValueError('account already open')
        self._open = True
        self._balance = 0

    def deposit(self, amount):
        if not self._open:
            raise ValueError('account not open')
        if amount <= 0:
            raise ValueError('amount must be greater than 0')
        self._balance += amount

    def withdraw(self, amount):
        if not self._open:
            raise ValueError('account not open')
        if amount <= 0:
            raise ValueError('amount must be greater than 0')
        if amount > self._balance:
            raise ValueError('amount must be less than balance')
        self._balance -= amount

    def close(self):
        if not self._open:
            raise ValueError('account not open')
        self._open = False
        self._balance = 0
