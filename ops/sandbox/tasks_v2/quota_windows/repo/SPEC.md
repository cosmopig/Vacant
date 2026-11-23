# Usage windows
## §1 Query semantics
Usage.add(tenant, time, units, event_id=None) records nonnegative integer units.
query(tenant,start,end) sums instants in [start,end), independent of input order.
ISO timestamps must have explicit offsets; compare in UTC, including distinct
instants with the same wall clock during a fall-back transition. Empty windows
return zero. End before start raises ValueError("end precedes start").
## §2 Cache and isolation
Query caches are scoped by tenant and normalized UTC bounds. Adding an event
invalidates that tenant's cached queries. An unknown tenant has zero usage.
Tenants are trimmed, case-sensitive nonempty strings. The three-positional
add signature still works; caller-owned event objects are never mutated.
## §3 IDs and errors
A non-None event_id is global: identical tenant/UTC instant/units is idempotent;
a conflict raises ValueError("event conflict") without modifying totals.
Naive/invalid time raises ValueError("time must include an offset"). Negative
or bool units raise ValueError("units must be an integer >= 0").
## §4 Persistence
codec.dumps/loads uses JSON list rows with tenant,time,units and optional id;
a legacy row without id still loads. dump uses UTC ISO times, preserves event
insertion order and produces independent row dictionaries via export().
count() returns the number of stored events (idempotent repeats are not stored).
