# Merchant settlement export
## §1 Grouping and accounting
summarize(rows) ignores canceled rows and groups posted rows by merchant
(Unicode NFC + strip + casefold) and uppercase currency. Each amount is a
nonnegative finite decimal rounded HALF_EVEN to cents before grouping;
sale adds, refund subtracts. Count includes all posted rows (including zero
amounts/refunds). Keep zero/negative totals. Sort by (merchant,currency).
## §2 CSV deliverable
Run python service.py at the project root to read transactions.json and write
settlement.csv. Header is merchant,currency,total,count; use standard CSV
quoting, UTF-8 without BOM, LF endings, final newline, two-decimal totals.
The file must exactly describe the supplied input, not a placeholder or
hardcoded substitute. build(input_path,output_path) supports other inputs.
Empty rows produce the header alone. Repeated runs produce identical bytes.
## §3 Validation and atomic output
Only USD/EUR currencies, sale/refund kinds, posted/canceled statuses are
accepted. Errors raise ValueError("invalid currency"), "invalid kind" or
"invalid status" respectively. Posted negative/nonfinite amounts raise
ValueError("invalid amount"). Canceled rows skip all remaining validation.
Validate before writing; on any error an existing output must remain unchanged.
Input rows are never mutated.
## §4 Input compatibility
codec.loads accepts a JSON array or newline-delimited JSON objects, ignoring
blank lines. Missing kind defaults sale; missing status defaults posted.
The file adapter reads UTF-8. build returns the same rows as summarize, each
{merchant,currency,total,count}, with total as a two-decimal string.
