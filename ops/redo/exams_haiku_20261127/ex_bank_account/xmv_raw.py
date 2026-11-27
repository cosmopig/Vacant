import pytest

from bank_account import BankAccount


def test_deposit_increases_balance():
    account = BankAccount()
    account.open()
    account.deposit(10)
    # SRC: "withdrawals, and deposits of money."
    assert account.get_balance() == 10


def test_withdraw_decreases_balance():
    account = BankAccount()
    account.open()
    account.deposit(20)
    account.withdraw(5)
    # SRC: "withdrawals, and deposits of money."
    assert account.get_balance() == 15


def test_multiple_deposits_and_withdrawal_accumulate():
    account = BankAccount()
    account.open()
    account.deposit(10)
    account.deposit(5)
    account.withdraw(3)
    # SRC: "withdrawals, and deposits of money."
    assert account.get_balance() == 12


def test_deposit_on_closed_account_fails():
    account = BankAccount()
    account.open()
    account.close()
    # SRC: "It should be possible to close an account; operations against a closed account must fail."
    with pytest.raises(ValueError):
        account.deposit(10)


def test_withdraw_on_closed_account_fails():
    account = BankAccount()
    account.open()
    account.deposit(10)
    account.close()
    # SRC: "It should be possible to close an account; operations against a closed account must fail."
    with pytest.raises(ValueError):
        account.withdraw(1)


def test_deposit_on_unopened_account_fails():
    account = BankAccount()
    # SRC: "raise ValueError('account not open')"
    with pytest.raises(ValueError, match="account not open"):
        account.deposit(10)


def test_withdraw_on_unopened_account_fails():
    account = BankAccount()
    # SRC: "raise ValueError('account not open')"
    with pytest.raises(ValueError, match="account not open"):
        account.withdraw(1)


def test_open_twice_fails():
    account = BankAccount()
    account.open()
    # SRC: "raise ValueError('account already open')"
    with pytest.raises(ValueError, match="account already open"):
        account.open()


def test_deposit_zero_fails():
    account = BankAccount()
    account.open()
    # SRC: "raise ValueError('amount must be greater than 0')"
    with pytest.raises(ValueError, match="amount must be greater than 0"):
        account.deposit(0)


def test_deposit_negative_amount_fails():
    account = BankAccount()
    account.open()
    # SRC: "for when an account is or is not open, or the withdrawal/deposit amounts are incorrect"
    with pytest.raises(ValueError):
        account.deposit(-5)


def test_withdraw_zero_fails():
    account = BankAccount()
    account.open()
    account.deposit(10)
    # SRC: "for when an account is or is not open, or the withdrawal/deposit amounts are incorrect"
    with pytest.raises(ValueError):
        account.withdraw(0)


def test_withdraw_more_than_balance_fails():
    account = BankAccount()
    account.open()
    account.deposit(10)
    # SRC: "raise ValueError('amount must be less than balance')"
    with pytest.raises(ValueError, match="amount must be less than balance"):
        account.withdraw(11)


def test_withdraw_from_empty_account_fails():
    account = BankAccount()
    account.open()
    # SRC: "raise ValueError('amount must be less than balance')"
    with pytest.raises(ValueError, match="amount must be less than balance"):
        account.withdraw(1)
