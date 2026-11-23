# Work-log report
## §1 Aggregation and idempotency
summarize(rows) consumes {id,owner,status,seconds} events. IDs are global;
exact duplicate rows count once, conflicting duplicate IDs raise
ValueError("event conflict"). Owners are NFC-normalized and stripped, and
remain case-sensitive. Group by owner, sum nonnegative integer seconds, and
count done events. Keep zero-second owners. Rows are {owner,seconds,done},
sorted by descending seconds, then owner.casefold(), then owner codepoint order.
## §2 Exact deliverable
Run python service.py at the root to read events.jsonl and write REPORT.md.
Start exactly with '# Work log', blank line, '| Owner | Seconds | Done |',
'|---|---:|---:|', each followed by LF. Data rows are
'| ESCAPED_OWNER | SECONDS | DONE |' plus LF. In owner text, escape each
backslash as two backslashes, then each pipe as backslash-pipe; replace CRLF,
lone CR and lone LF with a single space. No BOM or other text. Empty reports
contain only these header lines. Build must work on arbitrary supported inputs.
## §3 Validation and atomicity
Only open/done statuses are accepted, otherwise ValueError("invalid status").
Bool/negative seconds raise ValueError("seconds must be an integer >= 0").
Input events and returned lists never alias stored caller data. A failed
build leaves an existing output unchanged. Repeating a build is byte-identical.
## §4 Compatibility
codec.loads accepts JSONL with blank lines or a legacy JSON array; missing
status defaults open and seconds defaults 0. build(input_path="events.jsonl",
output_path="REPORT.md") returns the summary rows it writes. UTF-8 is used.
JSONL records are separated by LF (CRLF is accepted too); Unicode U+2028 and
U+0085 within JSON strings are field content, not record separators.
