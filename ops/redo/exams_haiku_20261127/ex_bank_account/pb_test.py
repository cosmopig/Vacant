"""Acceptance tests for the bank_account exercise.

Each check function is independent: it builds its own BankAccount objects
and makes its own calls. Expected values are derived from the requirements.
"""
import pytest

from bank_account import BankAccount


def _opened_account(initial_deposit=None):
    """Return a newly opened account, optionally with an initial deposit."""
    account = BankAccount()
    account.open()
    if initial_deposit is not None:
        account.deposit(initial_deposit)
    return account


def test_bank_account_can_be_created():
    """REQ: "Your task is to implement bank accounts supporting opening/closing, withdrawals, and deposits of money."

    Property: constructing a BankAccount succeeds and exposes the required operations.
    """
    account = BankAccount()
    assert account is not None
    for name in ("get_balance", "open", "deposit", "withdraw", "close"):
        assert callable(getattr(account, name, None)), f"missing method {name}"


def test_newly_opened_account_has_zero_balance():
    """REQ: "Your task is to implement bank accounts supporting opening/closing, withdrawals, and deposits of money."

    Property: an account that has just been opened, with no deposits, has a balance of 0.
    """
    account = BankAccount()
    account.open()
    assert account.get_balance() == 0


def test_balance_is_a_number():
    """REQ: "Your task is to implement bank accounts supporting opening/closing, withdrawals, and deposits of money."

    Property: get_balance returns a numeric value (not a bool or string).
    """
    account = _opened_account(10)
    balance = account.get_balance()
    assert isinstance(balance, (int, float))
    assert not isinstance(balance, bool)


def test_deposit_increases_balance():
    """REQ: "Your task is to implement bank accounts supporting opening/closing, withdrawals, and deposits of money."

    Example: open an account, deposit 100, the balance becomes 100.
    """
    account = _opened_account()
    account.deposit(100)
    assert account.get_balance() == 100


def test_deposits_accumulate():
    """REQ: "Your task is to implement bank accounts supporting opening/closing, withdrawals, and deposits of money."

    Property: successive deposits add up. Deposit 100 then 50 gives a balance of 150.
    """
    account = _opened_account()
    account.deposit(100)
    account.deposit(50)
    assert account.get_balance() == 150


def test_withdraw_decreases_balance():
    """REQ: "Your task is to implement bank accounts supporting opening/closing, withdrawals, and deposits of money."

    Example: deposit 100, withdraw 25, the balance becomes 75.
    """
    account = _opened_account(100)
    account.withdraw(25)
    assert account.get_balance() == 75


def test_get_balance_on_unopened_account_raises_value_error():
    """REQ: "This particular exercise requires that you use the raise statement to throw a `ValueError` for when an account is or is not open, or the withdrawal/deposit amounts are incorrect."

    Example: raise ValueError('account not open') when the account is not open.
    """
    account = BankAccount()
    with pytest.raises(ValueError) as excinfo:
        account.get_balance()
    assert str(excinfo.value).strip() != ""


def test_deposit_on_unopened_account_raises_value_error():
    """REQ: "This particular exercise requires that you use the raise statement to throw a `ValueError` for when an account is or is not open, or the withdrawal/deposit amounts are incorrect."

    Example: raise ValueError('account not open') when depositing into an account that is not open.
    """
    account = BankAccount()
    with pytest.raises(ValueError):
        account.deposit(10)


def test_withdraw_on_unopened_account_raises_value_error():
    """REQ: "This particular exercise requires that you use the raise statement to throw a `ValueError` for when an account is or is not open, or the withdrawal/deposit amounts are incorrect."

    Example: raise ValueError('account not open') when withdrawing from an account that is not open.
    """
    account = BankAccount()
    with pytest.raises(ValueError):
        account.withdraw(10)


def test_close_on_unopened_account_raises_value_error():
    """REQ: "This particular exercise requires that you use the raise statement to throw a `ValueError` for when an account is or is not open, or the withdrawal/deposit amounts are incorrect."

    Property: closing an account that is not open is an error and raises ValueError.
    """
    account = BankAccount()
    with pytest.raises(ValueError):
        account.close()


def test_open_on_already_open_account_raises_value_error():
    """REQ: "raise ValueError('account already open')"

    Example: opening an account that is already open raises ValueError.
    """
    account = _opened_account()
    with pytest.raises(ValueError) as excinfo:
        account.open()
    assert str(excinfo.value).strip() != ""


def test_deposit_zero_raises_value_error():
    """REQ: "raise ValueError('amount must be greater than 0')"

    Property: depositing an amount of 0 is incorrect and raises ValueError.
    """
    account = _opened_account()
    with pytest.raises(ValueError):
        account.deposit(0)


def test_deposit_negative_amount_raises_value_error():
    """REQ: "raise ValueError('amount must be greater than 0')"

    Property: depositing a negative amount is incorrect and raises ValueError.
    """
    account = _opened_account()
    with pytest.raises(ValueError):
        account.deposit(-5)


def test_withdraw_zero_raises_value_error():
    """REQ: "raise ValueError('amount must be greater than 0')"

    Property: withdrawing an amount of 0 is incorrect and raises ValueError.
    """
    account = _opened_account(10)
    with pytest.raises(ValueError):
        account.withdraw(0)


def test_withdraw_negative_amount_raises_value_error():
    """REQ: "raise ValueError('amount must be greater than 0')"

    Property: withdrawing a negative amount is incorrect and raises ValueError.
    """
    account = _opened_account(10)
    with pytest.raises(ValueError):
        account.withdraw(-5)


def test_withdraw_more_than_balance_raises_value_error():
    """REQ: "# withdrawal is too big / raise ValueError('amount must be less than balance')"

    Example: with a balance of 10, withdrawing 20 raises ValueError.
    """
    account = _opened_account(10)
    with pytest.raises(ValueError):
        account.withdraw(20)


def test_failed_withdraw_leaves_balance_unchanged():
    """REQ: "# withdrawal is too big / raise ValueError('amount must be less than balance')"

    Invariant: a withdrawal that is rejected does not change the balance.
    With a balance of 10, a rejected withdrawal of 20 leaves the balance at 10.
    """
    account = _opened_account(10)
    with pytest.raises(ValueError):
        account.withdraw(20)
    assert account.get_balance() == 10


def test_failed_deposit_leaves_balance_unchanged():
    """REQ: "# incorrect withdrawal/deposit amount / raise ValueError('amount must be greater than 0')"

    Invariant: a deposit that is rejected does not change the balance.
    With a balance of 10, a rejected deposit of -5 leaves the balance at 10.
    """
    account = _opened_account(10)
    with pytest.raises(ValueError):
        account.deposit(-5)
    assert account.get_balance() == 10


def test_error_messages_are_meaningful_and_type_is_value_error():
    """REQ: "When you do this, you should always include a **meaningful error message** to indicate what the source of the error is."

    Property: the raised exception is a ValueError and carries a non-empty message.
    """
    account = _opened_account()
    with pytest.raises(ValueError) as excinfo:
        account.deposit(0)
    assert isinstance(excinfo.value, ValueError)
    assert str(excinfo.value).strip() != ""


def test_open_then_close_succeeds():
    """REQ: "It should be possible to close an account; operations against a closed account must fail."

    Property: an open account can be closed without raising an error.
    """
    account = _opened_account()
    account.close()


def test_deposit_after_close_fails():
    """REQ: "It should be possible to close an account; operations against a closed account must fail."

    Property: depositing into a closed account raises ValueError.
    """
    account = _opened_account()
    account.close()
    with pytest.raises(ValueError):
        account.deposit(10)


def test_withdraw_after_close_fails():
    """REQ: "It should be possible to close an account; operations against a closed account must fail."

    Property: withdrawing from a closed account raises ValueError.
    """
    account = _opened_account(10)
    account.close()
    with pytest.raises(ValueError):
        account.withdraw(5)


def test_get_balance_after_close_fails():
    """REQ: "It should be possible to close an account; operations against a closed account must fail."

    Property: reading the balance of a closed account raises ValueError.
    """
    account = _opened_account(10)
    account.close()
    with pytest.raises(ValueError):
        account.get_balance()


def test_close_on_already_closed_account_raises_value_error():
    """REQ: "This particular exercise requires that you use the raise statement to throw a `ValueError` for when an account is or is not open, or the withdrawal/deposit amounts are incorrect."

    Property: closing an account that is already closed (so not open) raises ValueError.
    """
    account = _opened_account()
    account.close()
    with pytest.raises(ValueError):
        account.close()


def test_separate_accounts_have_independent_balances():
    """REQ: "Your task is to implement bank accounts supporting opening/closing, withdrawals, and deposits of money."

    Property: operations on one account do not change the balance of another account.
    """
    first = _opened_account()
    second = _opened_account()
    first.deposit(100)
    second.deposit(40)
    first.withdraw(30)
    assert first.get_balance() == 70
    assert second.get_balance() == 40
