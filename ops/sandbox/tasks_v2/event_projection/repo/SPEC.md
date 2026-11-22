# Inventory projection
## §1 Replay
Projection.apply(events) accepts {id,sku,version,kind,quantity?} events. kind is
"set" (quantity required, nonnegative integer) or "delete". Versions are
positive integers scoped by SKU; process in input order. An event older than
or equal to the SKU's current version is ignored, including after deletion.
items() returns active {sku,quantity,version} rows sorted by SKU.
## §2 Event IDs
Event IDs are global. An identical repeated ID/event is a no-op; a different
reuse raises ValueError("event conflict"). Even ignored old-version events
reserve their IDs after a successful batch. Inputs and returned views are detached.
## §3 Atomicity and invalidation
The entire batch is atomic. Any invalid event or ID conflict leaves state,
event-ID history and any previously cached items view unchanged. Successful
writes invalidate the cached view. Unknown kind raises ValueError("unknown kind").
Invalid quantity raises ValueError("quantity must be an integer >= 0").
## §4 Snapshots
codec.dumps emits {version:2,state:{sku:{version,quantity}},seen:{id:event}};
quantity=null denotes a tombstone. loads roundtrips ID history and tombstones.
Legacy [{sku,quantity}] rows load at version 0 with no IDs. Empty input is a no-op.
