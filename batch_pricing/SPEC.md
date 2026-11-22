# Batch invoices
## §1 Graduated pricing
quote(quantity, tiers, discount="0") returns a two-decimal string. Tiers are
ordered (upper,rate) pairs: upper is a cumulative inclusive unit count; final
upper is None (unbounded). Each unit is charged at its own band's nonnegative
decimal rate. quantity is a nonnegative integer (bool rejected). Zero costs 0.00.
## §2 Rounding and coupons
Compute the full unrounded line sum, multiply by (1-discount), then quantize
once with ROUND_HALF_EVEN. discount is decimal in [0,1]. Decimal(str(value))
conversion is required, not binary float arithmetic or per-band rounding.
## §3 Validation and atomic batches
Tiers must be nonempty, finite-rate, strictly increasing positive integer
bounds with only the final bound None; otherwise ValueError("invalid tiers").
Invalid discounts raise ValueError("invalid discount"). invoice(lines,tiers,
coupons=None) accepts {id,quantity,coupon?} rows. Unknown coupon raises
KeyError(code). Duplicate line ids raise ValueError("duplicate line id").
Inputs are unchanged on success/failure. Results preserve line order and are
{lines:[{id,total}],total}, where total is the sum of already-rounded lines.
Empty batches yield {lines:[],total:"0.00"}.
## §4 Legacy wire format
codec.loads accepts list pairs and legacy {upper_as_string:rate} with "*"
meaning None; numeric keys are sorted numerically, not lexicographically.
codec.dumps emits ordered list pairs. The two-argument quote call still works.
