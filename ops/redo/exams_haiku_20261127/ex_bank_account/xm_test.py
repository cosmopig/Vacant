import pytest

from bank_account import BankAccount


def test_newly_opened_account_has_zero_balance():
    account = BankAccount()
    account.open()
    assert account.get_balance() == 0


def test_deposit_increases_balance():
    account = BankAccount()
    account.open()
    account.deposit(100)
    assert account.get_balance() == 100
    account.deposit(50)
    assert account.get_balance() == 150


def test_withdraw_decreases_balance():
    account = BankAccount()
    account.open()
    account.deposit(100)
    account.withdraw(30)
    assert account.get_balance() == 70


def test_cannot_open_an_already_open_account():
    account = BankAccount()
    account.open()
    with pytest.raises(ValueError) as exc_info:
        account.open()
    assert str(exc_info.value) != ""


def test_cannot_deposit_into_unopened_account():
    account = BankAccount()
    with pytest.raises(ValueError):
        account.deposit(10)


def test_cannot_withdraw_from_unopened_account():
    account = BankAccount()
    with pytest.raises(ValueError):
        account.withdraw(10)


def test_cannot_deposit_into_closed_account():
    account = BankAccount()
    account.open()
    account.close()
    with pytest.raises(ValueError):
        account.deposit(10)


def test_cannot_withdraw_from_closed_account():
    account = BankAccount()
    account.open()
    account.deposit(10)
    account.close()
    with pytest.raises(ValueError):
        account.withdraw(5)


def test_cannot_get_balance_of_closed_account():
    account = BankAccount()
    account.open()
    account.close()
    with pytest.raises(ValueError):
        account.get_balance()


def test_zero_or_negative_deposit_is_rejected_and_balance_unchanged():
    account = BankAccount()
    account.open()
    account.deposit(100)
    with pytest.raises(ValueError) as exc_info:
        account.deposit(0)
    assert str(exc_info.value) != ""
    with pytest.raises(ValueError):
        account.deposit(-10)
    assert account.get_balance() == 100


def test_zero_or_negative_withdrawal_is_rejected_and_balance_unchanged():
    account = BankAccount()
    account.open()
    account.deposit(100)
    with pytest.raises(ValueError) as exc_info:
        account.withdraw(0)
    assert str(exc_info.value) != ""
    with pytest.raises(ValueError):
        account.withdraw(-5)
    assert account.get_balance() == 100


def test_cannot_withdraw_more_than_balance_and_balance_unchanged():
    account = BankAccount()
    account.open()
    account.deposit(50)
    with pytest.raises(ValueError) as exc_info:
        account.withdraw(51)
    assert str(exc_info.value) != ""
    assert account.get_balance() == 50


def test_separate_accounts_have_independent_balances():
    first = BankAccount()
    second = BankAccount()
    first.open()
    second.open()
    first.deposit(200)
    second.deposit(40)
    second.withdraw(15)
    assert first.get_balance() == 200
    assert second.get_balance() == 25
