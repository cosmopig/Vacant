# Credit ledger
## §1 Transfers
Ledger(opening) takes a mapping of account names to nonnegative amounts.
transfer(source, target, amount, key=None) moves a positive amount between
different existing accounts; the three-argument signature remains supported.
All amounts are Decimal(str(value)) rounded to cents with ROUND_HALF_EVEN
before positivity/affordability checks. balance(name) returns Decimal cents.
## §2 Atomicity and caches
A successful transfer invalidates cached balances for both accounts. An
unaffordable transfer raises ValueError("insufficient funds") and changes
neither balances nor the idempotency registry. Nonpositive amounts raise
ValueError("amount must be positive"). Unknown accounts raise KeyError(name).
Same-account transfers raise ValueError("accounts must differ").
total() returns the sum of all account balances, including after a warm read.
## §3 Idempotency
A repeated non-None key with the same source, target and rounded amount is a
no-op. A conflicting reuse raises ValueError("key conflict") without mutation.
Failed attempts do not reserve a key. None always means a fresh transfer.
## §4 Wire compatibility
codec.dumps/loads roundtrip balances and key history. Version 2 is a JSON
object with version=2, balances (two-decimal strings), and keys (key mapped to
[source,target,two-decimal amount]). A legacy flat balances object still loads.
dump order is deterministic (sort_keys). Public snapshots never alias state.
