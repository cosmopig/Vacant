# Retry queue
## §1 Ordering and claiming
Queue.push(id,payload,due=0) adds a unique job with integer due >= 0 and
attempts=0. ready(now,limit=None) claims due <= now jobs, sorted by (due,
insertion sequence), and removes them from the pending queue. limit=0 claims
nothing; None is unbounded. Claim results and push payloads are deep copies.
## §2 Retry and acknowledgement
retry(job,now,base=2,cap=60) requeues a claimed job, increments attempts, and
schedules now + min(cap, base * 2**old_attempts). The original insertion
sequence is retained. ack(job) releases its ID; IDs remain reserved while
claimed or pending. Retrying/acking a job not currently claimed raises
ValueError("job is not claimed"). A stale job copy after retry cannot be acked.
## §3 Validation
Duplicate IDs raise ValueError("duplicate job"). Negative/bool limits raise
ValueError("limit must be an integer >= 0"); failed operations do not mutate
queue state. now/due/base/cap are nonnegative integers; base=0 is valid.
## §4 Persistence and compatibility
codec.dumps/loads preserve pending order, attempts, reserved IDs and claimed
jobs. A legacy JSON list of {id,payload,due} rows loads with attempts=0 and
sequence equal to list position. export() is detached. Empty queues roundtrip.
